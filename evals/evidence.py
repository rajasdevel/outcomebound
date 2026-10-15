"""Digests that say whether what a run was judged on is still what is on disk.

`--regrade` judges a kept workspace again without a model call. It needs two facts from the
original run: that the workspace is as the run left it, and that the fixture's files under
`evals/` (its definition, the graders and what they share) are as the run was graded with.
Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

# A fixture's setup and plan name the fixture directories they share as `../<name>/` or
# `fixtures/<name>/`; those are part of what grades it.
SHARED = re.compile(r"(?:\.\./|fixtures/)([A-Za-z0-9_-]+)/")
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


def grading_digest(evals: Path, fixture: str) -> str:
    """The SHA-256 of the files that grade `fixture` under `evals`: its fixture directory, each
    fixture directory its files name as shared, the files directly in `fixtures/`, and the
    graders. Each file counts by its path relative to `evals` and its bytes."""

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
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        _feed(digest, path.relative_to(evals).as_posix(), path.read_bytes())
    return digest.hexdigest()


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
