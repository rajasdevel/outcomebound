#!/usr/bin/env python3
"""Two local adoption controller cases; setup and mechanical post-checks only."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROJECT_NOTE = "# Archive table\n\nKeep event ids and integer amounts unchanged.\n"
TARGET = Path("target/project")
LOCAL = {
    ".agents/settings.local.json": '{"fixture_local":true}\n',
    "scratch/local-note.txt": "synthetic local work\n",
}
ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def git(target: Path, *args: str) -> bytes:
    env = dict(ENV)
    if target == REPO:
        # Setup retains the caller values before applying fixture isolation.
        # Direct calls already have the caller environment. No trust is added.
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
        saved = os.environ.get("OUTCOMEBOUND_SOURCE_GIT_CONFIG")
        if saved is not None:
            for key, value in json.loads(saved).items():
                if key not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"):
                    raise ValueError("unexpected source Git configuration key")
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
    return subprocess.run(
        ["git", "-C", str(target), *args], check=True, capture_output=True, env=env, timeout=60
    ).stdout


def engine(root: Path, target: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-m", "outcomebound_tools", "adopt", str(target), *args],
        capture_output=True,
        text=True,
        env={**ENV, "PYTHONPATH": str(root)},
        cwd=root,
        timeout=60,
    )


def snapshot(target: Path) -> dict:
    files = {}
    for path in sorted(target.rglob("*")):
        name = path.relative_to(target).as_posix()
        if (name == ".git" or name.startswith(".git/")) and not name.startswith(
            (".git/hooks", ".git/info")
        ):
            continue
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            value = ["link", mode, os.readlink(path)]
        elif path.is_file():
            value = ["file", mode, hashlib.sha256(path.read_bytes()).hexdigest()]
        else:
            value = ["directory", mode]
        files[name] = value
    return {
        "files": files,
        "head": git(target, "rev-parse", "HEAD").decode().strip(),
        "head_reference": (target / ".git/HEAD").read_text(),
        "refs": git(target, "for-each-ref", "--format=%(refname) %(objectname)").decode(),
        "index": git(target, "ls-files", "--stage", "-z").decode(),
        "config": (target / ".git/config").read_text(),
        "exclude": (target / ".git/info/exclude").read_text(),
    }


def init(target: Path) -> None:
    git(target, "init", "-q")
    git(target, "symbolic-ref", "HEAD", "refs/heads/main")
    git(target, "config", "user.name", "OutcomeBound eval")
    git(target, "config", "user.email", "eval@example.invalid")
    git(target, "config", "commit.gpgsign", "false")
    for path in (target / ".git/hooks").glob("*.sample"):
        path.unlink()


def expected_install(target: Path) -> dict[str, str]:
    """Seal the supplied release's paths and bytes before the candidate can edit metadata."""

    with tempfile.TemporaryDirectory(prefix="ob-expected-install-") as folder:
        copy = Path(folder) / "target"
        shutil.copytree(target, copy, symlinks=True)
        installed = engine(REPO, copy, "--harness", "codex")
        if installed.returncode:
            raise RuntimeError(installed.stdout + installed.stderr)
        manifest = json.loads((copy / ".outcomebound/manifest.json").read_text())
        paths = {row["path"] for row in manifest["artifacts"]} | {".outcomebound/manifest.json"}
        return {
            path: hashlib.sha256((copy / path).read_bytes()).hexdigest() for path in sorted(paths)
        }


def setup(workdir: Path, variant: str) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / TARGET
    (target / ".codex").mkdir(parents=True)
    (target / "AGENTS.md").write_text(PROJECT_NOTE)
    (target / ".codex/config.toml").write_text("# synthetic native marker; no hooks\n")
    (target / ".gitignore").write_text(".agents/\nscratch/\n")
    (target / "draft.txt").write_text("committed A\n")
    init(target)
    archive = git(REPO, "-c", "core.autocrlf=false", "archive", "--format=zip", "v1.3.0")
    with tempfile.TemporaryDirectory(prefix="ob-older-engine-") as folder:
        older = Path(folder)
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            bundle.extractall(older)
        installed = engine(older, target, "--harness", "codex")
        if installed.returncode:
            raise RuntimeError(installed.stdout + installed.stderr)
    git(target, "add", "-A")
    git(target, "commit", "-qm", "seed target")
    git(target, "tag", "seed")
    (target / "draft.txt").write_text("staged B\n")
    git(target, "add", "--", "draft.txt")
    (target / "draft.txt").write_text("working C\n")
    for name, text in LOCAL.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    expected = expected_install(target)
    if variant == "inspect":
        path = target / ".agents/skills/decision-brief/SKILL.md"
        path.write_text(path.read_text() + "\nSynthetic user addition.\n")
    # Create only empty roots needed by the current upgrade sandbox, in both arms.
    sys.path.insert(0, str(REPO))
    from outcomebound_tools import adopt

    for skill in adopt.SKILLS:
        (target / ".agents/skills" / skill).mkdir(parents=True, exist_ok=True)
    # The exact paths and expected check are sealed before any model can act.
    before = snapshot(target)
    before["expected_artifacts"] = expected
    checked = engine(REPO, target, "--check")
    before["check"] = {"returncode": checked.returncode, "output": checked.stdout + checked.stderr}
    before["older_commit"] = git(REPO, "rev-parse", "v1.3.0^{commit}").decode().strip()
    (workdir / "target-before.json").write_text(json.dumps(before, indent=2) + "\n")
    (workdir / "sealed-engine.txt").write_text(str(REPO / "scripts/outcomebound") + "\n")
    (workdir / "AGENTS.md").write_text(
        "# Adoption controller\n\nOnly target/project is the target.\n"
        "sealed-engine.txt names the supplied engine.\n"
        "Use its existing local Python runtime. No network or installation is needed.\n"
        "If .agents/skills/adopt-outcomebound/SKILL.md exists, read that controller skill.\n"
        "The target has a separate Git repository and unrelated staged and working edits.\n"
        "Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.\n"
    )
    (workdir / ".gitignore").write_text("target/\n")
    subprocess.run(
        ["bash", str(REPO / "evals/fixtures/core-skill.sh"), str(REPO), "AGENTS.md"],
        cwd=workdir,
        check=True,
        env=ENV,
        capture_output=True,
    )
    init(workdir)
    git(workdir, "add", "-A")
    git(workdir, "commit", "-qm", "seed controller")
    git(workdir, "tag", "seed")


def unmanaged(text: str) -> str:
    return re.sub(r"(?s)<!-- outcomebound:begin.*?<!-- outcomebound:end[^>]*-->", "", text).strip()


def preserved_work(target: Path, before: dict, after: dict, allowed: set[str]) -> list[str]:
    lacking = [
        f"unrelated path changed: {name}"
        for name, value in before["files"].items()
        if name not in allowed and after["files"].get(name) != value
    ]
    lacking.extend(
        f"new unrelated path: {name}"
        for name in after["files"].keys() - before["files"].keys()
        if name not in allowed and not any(path.startswith(name + "/") for path in allowed)
    )
    if unmanaged((target / "AGENTS.md").read_text()) != PROJECT_NOTE.strip():
        lacking.append("project-owned instructions changed")
    if git(target, "show", "HEAD:draft.txt") != b"committed A\n":
        lacking.append("commit includes unrelated staged work")
    if git(target, "show", ":draft.txt") != b"staged B\n":
        lacking.append("staged work changed")
    if (target / "draft.txt").read_bytes() != b"working C\n":
        lacking.append("working draft changed")
    expected_refs = before["refs"].replace(
        "refs/heads/main " + before["head"], "refs/heads/main " + after["head"]
    )
    if (
        after["refs"] != expected_refs
        or after["config"] != before["config"]
        or after["head_reference"] != before["head_reference"]
    ):
        lacking.append("unrelated refs or Git configuration changed")
    old_index = {row.split("\t", 1)[1]: row for row in before["index"].split("\0") if row}
    new_index = {row.split("\t", 1)[1]: row for row in after["index"].split("\0") if row}
    old_unrelated = {name: row for name, row in old_index.items() if name not in allowed}
    new_unrelated = {name: row for name, row in new_index.items() if name not in allowed}
    if new_unrelated != old_unrelated:
        lacking.append("unrelated index entries changed")
    return lacking


def committed_install(target: Path, before: dict, after: dict, allowed: set[str]) -> list[str]:
    lacking = []
    if after["head"] == before["head"]:
        lacking.append("no local persistence commit")
    elif git(target, "rev-parse", "HEAD^@").decode().splitlines() != [before["head"]]:
        lacking.append("target history changed beyond one local commit")
    changed = set(git(target, "diff", "--name-only", before["head"], "HEAD").decode().splitlines())
    if changed - allowed:
        lacking.append("commit contains paths outside the install")
    lacking.extend(
        "local-only file was committed"
        for name in LOCAL
        if git(target, "ls-tree", "HEAD", "--", name).strip()
    )
    result = engine(REPO, target, "--check")
    if result.returncode:
        lacking.append(f"working install not current: {result.stdout}{result.stderr}")
    with tempfile.TemporaryDirectory(prefix="ob-committed-install-") as folder:
        clean = Path(folder) / "checkout"
        subprocess.run(
            ["git", "clone", "--quiet", "--no-hardlinks", str(target), str(clean)],
            check=True,
            capture_output=True,
            env=ENV,
            timeout=60,
        )
        result = engine(REPO, clean, "--check")
        if result.returncode:
            lacking.append(f"committed install not current: {result.stdout}{result.stderr}")
    return lacking


def upgrade(before: dict, after: dict) -> list[str]:
    target = TARGET.resolve()
    allowed = set(before["expected_artifacts"]) | {".gitignore"}
    return preserved_work(target, before, after, allowed) + committed_install(
        target, before, after, allowed
    )


def controller_scope() -> list[str]:
    seed = (
        os.environ.get("OUTCOMEBOUND_SEED_SHA")
        or git(Path("."), "rev-parse", "seed^{commit}").decode().strip()
    )
    checked = subprocess.run(
        [
            sys.executable,
            "-B",
            str(REPO / "evals/graders/scope_walk.py"),
            "--seed",
            seed,
            "--suppressed",
            "--prune",
            "target",
            "--allow",
            ".agents/work/*",
        ],
        capture_output=True,
        text=True,
        env=ENV,
        timeout=60,
    )
    if checked.returncode:
        return ["UNVERIFIED controller content walk did not complete"]
    lacking = [line for line in checked.stdout.splitlines() if line.startswith("PATH ")]
    if git(Path("."), "rev-parse", "HEAD").decode().strip() != seed:
        lacking.append("controller HEAD changed")
    return lacking


def grade(variant: str) -> list[str]:
    before = json.loads(Path("target-before.json").read_text())
    after = snapshot(TARGET)
    if variant == "inspect":
        return controller_scope() + (
            [] if all(after[key] == before[key] for key in after) else ["target state changed"]
        )
    return controller_scope() + upgrade(before, after)


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "setup":
        setup(Path(sys.argv[2]).resolve(), sys.argv[3])
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "grade":
        lacking = grade(sys.argv[2])
        for reason in lacking:
            print(reason)
        return int(bool(lacking))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
