"""Digests that say whether what a run was judged on is still what is on disk.

`--regrade` judges a kept workspace again without a model call. It needs two facts from the
original run: that the workspace is as the run left it, and that the fixture's files under
`evals/` (its definition, the graders and what they share) are as the run was graded with.
A run also seals its graders: they stay outside the workspace in a stage, and what the stage and
the grading files held before the call must be what they hold after it. The functions here name
those files, digest them and copy them. Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

# A fixture's setup, plan and graders name the fixture directories they share as `../<name>/`,
# `fixtures/<name>/` or `parent / "<name>/`; those are part of what grades it.
SHARED = re.compile(r"(?:\.\./|fixtures/|parent\s*/\s*\")([A-Za-z0-9_-]+)/")
SKIP_DIRS = {"__pycache__", ".git"}


def _feed(digest: hashlib._Hash, label: str, data: bytes) -> None:
    digest.update(f"{label}\0{len(data)}\0".encode())
    digest.update(data)


def _files(root: Path) -> list[Path]:
    """Each file under `root`, sorted, not entering a `__pycache__` or `.git` folder."""

    found = []
    for folder, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in SKIP_DIRS)
        found += [Path(folder) / name for name in sorted(files)]
    return found


def grading_files(evals: Path, fixture: str) -> list[Path]:
    """The files that grade `fixture` under `evals`, sorted: its fixture directory, each
    fixture directory its files name as shared, the files directly in `fixtures/`, and the
    graders."""

    fixtures = evals / "fixtures"
    folders: set[str] = set()
    pending = [fixture]
    while pending:
        name = pending.pop()
        if name in folders or not (fixtures / name).is_dir():
            continue
        folders.add(name)
        for path in _files(fixtures / name):
            text = path.read_text(encoding="utf-8", errors="replace")
            pending += SHARED.findall(text)
    paths = [path for path in sorted(fixtures.iterdir()) if path.is_file()]
    for folder in sorted(folders):
        paths += _files(fixtures / folder)
    paths += _files(evals / "graders")
    return sorted(set(paths))


def grading_hashes(evals: Path, fixture: str) -> dict[str, str]:
    """The SHA-256 of each file that grades `fixture`, by its path relative to `evals`."""

    return {
        path.relative_to(evals).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in grading_files(evals, fixture)
    }


def grading_digest(evals: Path, fixture: str) -> str:
    """The SHA-256 of the files that grade `fixture` under `evals`. Each file counts by its path
    relative to `evals` and its bytes."""

    digest = hashlib.sha256()
    for path in grading_files(evals, fixture):
        _feed(digest, path.relative_to(evals).as_posix(), path.read_bytes())
    return digest.hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    """The SHA-256 of each file under `root`, by relative path; a link by its target. A
    `__pycache__` or `.git` folder is not entered."""

    found = {}
    for path in _files(root):
        name = path.relative_to(root).as_posix()
        found[name] = (
            "link:" + os.readlink(path)
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
    return found


def tree_digest(root: Path) -> str:
    """One SHA-256 for the files under `root`, as `tree_hashes` names them."""

    digest = hashlib.sha256()
    for name, value in sorted(tree_hashes(root).items()):
        _feed(digest, name, value.encode())
    return digest.hexdigest()


def changed(before: dict[str, str], now: dict[str, str]) -> list[str]:
    """The names whose digest differs between two maps, or that only one of them holds."""

    return sorted(name for name in before.keys() | now.keys() if before.get(name) != now.get(name))


def _skipped(folder: str, names: list[str]) -> list[str]:
    """The folders of `names` that `tree_hashes` does not enter, so the copy holds no file the
    seal did not digest, such as a `__pycache__` written into the stage during the call."""

    return [
        name for name in names if name in SKIP_DIRS and os.path.isdir(os.path.join(folder, name))
    ]


def seal(stage: Path, plan: Path, evals: Path, fixture: str, destination: Path) -> str:
    """Copy what grades `fixture` into the new folder `destination`, and return its digest: the
    stage as it stands, the fixture's `post.plan.json` and the grading files, which keep their
    paths under `evals/`. A `__pycache__` or `.git` folder of the stage is not copied."""

    shutil.copytree(stage, destination, symlinks=True, ignore=_skipped)
    shutil.copy2(plan, destination / "post.plan.json")
    for path in grading_files(evals, fixture):
        target = destination / "evals" / path.relative_to(evals)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return tree_digest(destination)


def _git(workdir: Path, env: dict[str, str], *arguments: str) -> bytes | None:
    try:
        done = subprocess.run(
            ["git", *arguments], cwd=workdir, capture_output=True, env=env, timeout=120
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _untracked(workdir: Path, digest: hashlib._Hash, name: str) -> None:
    """Feed the content of one untracked entry: a file, a link's target, or each file of a
    folder (a nested repository is listed as a folder), leaving out `.git` folders."""

    path = workdir / name.rstrip("/")
    try:
        if path.is_symlink():
            _feed(digest, f"link {name}", os.readlink(path).encode())
        elif path.is_dir():
            for inner in _files(path):
                _feed(digest, f"file {inner.relative_to(workdir).as_posix()}", inner.read_bytes())
        else:
            _feed(digest, f"file {name}", path.read_bytes())
    except OSError as problem:
        _feed(digest, f"unreadable {name}", type(problem).__name__.encode())


def workspace_digest(workdir: Path, env: dict[str, str]) -> str | None:
    """The SHA-256 of what a run left in its workspace: the Git status, `HEAD`, the diff of
    tracked files against `HEAD`, and the content of every untracked file (ignored ones
    included). None where Git cannot say. Nothing under a `.git` folder is read, so a later
    `git status` cannot change it."""

    parts = {
        "status": _git(workdir, env, "status", "--porcelain=v1", "-z"),
        "head": _git(workdir, env, "rev-parse", "--verify", "HEAD"),
        "diff": _git(workdir, env, "diff", "HEAD", "--binary", "--no-ext-diff"),
        "others": _git(workdir, env, "ls-files", "-z", "--others"),
    }
    if any(value is None for value in parts.values()):
        return None
    digest = hashlib.sha256()
    for label, value in parts.items():
        _feed(digest, label, value or b"")
    for name in sorted(
        filter(None, (parts["others"] or b"").decode("utf-8", "replace").split("\0"))
    ):
        _untracked(workdir, digest, name)
    return digest.hexdigest()


def sealed_changes(
    copy: Path, stage_files: dict[str, str], grading: dict[str, str], fixture: str
) -> list[str]:
    """What the sealed copy `copy` holds that differs from what was sealed before the call: the
    stage's files (`stage_files`, by path) and the grading files (`grading`, by path under
    `evals/`). A process that outlived the call could change either between the check and the
    copy."""

    held = tree_hashes(copy)
    staged = {
        name: value
        for name, value in held.items()
        if name != "post.plan.json" and not name.startswith("evals/")
    }
    return [
        *(f"stage/{name}" for name in changed(stage_files, staged)),
        *(f"evals/{name}" for name in changed(grading, grading_hashes(copy / "evals", fixture))),
    ]
