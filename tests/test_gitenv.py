"""Every Git subprocess in the engine runs under the C locale.

The engine reads Git's own messages, and a non-English locale rewrites them. One
helper composes the child environment, and this node holds every call site to it.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from tests.portable import write

ROOT = Path(__file__).resolve().parent.parent
RUNNERS = {"run", "Popen", "check_output", "check_call", "call"}


def _git_calls(tree: ast.AST) -> list[ast.Call]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        callee = node.func
        if not (
            isinstance(callee, ast.Attribute)
            and callee.attr in RUNNERS
            and isinstance(callee.value, ast.Name)
            and callee.value.id == "subprocess"
        ):
            continue
        argv = node.args[0]
        if isinstance(argv, ast.List) and argv.elts and _names_git(argv.elts[0]):
            found.append(node)
    return found


def _names_git(first: ast.expr) -> bool:
    """Whether an argv's first word is `"git"`, or `programs.require("git", ...)`, which finds it
    on PATH's absolute entries."""

    if isinstance(first, ast.Constant):
        return first.value == "git"
    return (
        isinstance(first, ast.Call)
        and isinstance(first.func, ast.Attribute)
        and first.func.attr == "require"
        and bool(first.args)
        and isinstance(first.args[0], ast.Constant)
        and first.args[0].value == "git"
    )


def _environment_keyword(call: ast.Call) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == "env"), None)


def test_every_git_subprocess_runs_under_the_git_environment() -> None:
    """Each `subprocess.run(["git", …])` in the engine, and each that starts Git through
    `programs.require("git")`, passes `env=git_environment(…)`, and none runs git through a
    shell."""

    unrouted = []
    shelled = []
    seen = 0
    for path in sorted((ROOT / "outcomebound_tools").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _git_calls(tree):
            seen += 1
            value = _environment_keyword(call)
            routed = (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "git_environment"
            )
            if not routed:
                unrouted.append(f"{path.name}:{call.lineno}")
            # And never through a shell.
            if any(keyword.arg == "shell" for keyword in call.keywords):
                shelled.append(f"{path.name}:{call.lineno}")
    assert seen >= 1, "the survey found no git call site, so it reads nothing"
    assert unrouted == [], unrouted
    assert shelled == [], shelled


def test_the_git_environment_pins_the_locale_and_keeps_the_rest() -> None:
    from outcomebound_tools.gitenv import git_environment

    composed = git_environment({"PATH": "/usr/bin", "LC_ALL": "de_DE.UTF-8", "HOME": "/h"})
    assert composed["LC_ALL"] == "C"
    assert composed["LANGUAGE"] == "C"
    assert composed["PATH"] == "/usr/bin" and composed["HOME"] == "/h"
    inherited = git_environment()
    assert inherited["LC_ALL"] == "C" and inherited["LANGUAGE"] == "C"


def _hostile_repository(tmp_path: Path) -> tuple[Path, Path]:
    """A repository whose own `.git/config` names a `core.fsmonitor` program that leaves a
    marker when it runs."""

    root = tmp_path / "target"
    (root / ".claude" / "skills" / "mine").mkdir(parents=True)
    write(root / ".claude" / "skills" / "mine" / "SKILL.md", "x\n")
    marker = tmp_path / "fsmonitor-ran"
    hook = tmp_path / "hook.sh"
    # Git runs the program through its shell, so the program and the file it makes are named with
    # forward slashes, which Git's shell on Windows reads where it would eat a backslash, and the
    # script is LF text, since `#!/bin/sh\r` names no shell. The redirection is the shell's own,
    # so the script needs no tool of the shell's folder.
    write(hook, f"#!/bin/sh\n: > '{marker.as_posix()}'\n")
    hook.chmod(0o755)
    commands = (
        ["init", "-q", "."],
        ["add", "-A"],
        ["-c", "user.email=a@example.org", "-c", "user.name=a", "commit", "-qm", "i"],
        ["config", "core.fsmonitor", hook.as_posix()],
    )
    for arguments in commands:
        subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True)
    return root, marker


def test_no_read_of_a_target_runs_the_fsmonitor_program_its_git_config_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from outcomebound_tools import (
        adopt,
        discovery,
        finish_check,
        floor,
        harness_roots,
        instruction_audit,
        scaffold,
        tickets_git,
    )

    root, marker = _hostile_repository(tmp_path)
    # Control: plain Git runs the program, so each check below can fail.
    subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True)
    assert marker.exists()
    marker.unlink()

    tickets_git.git(root, "status", "--porcelain")
    harness_roots._tracked(root, ".claude")
    finish_check._git(root, "status", "--porcelain")
    floor._git(root, "status", "--porcelain")
    adopt._git(root, "status", "--porcelain")
    instruction_audit._git_status(root, "status", "--porcelain")
    scaffold._git_listed(root)
    discovery.main([str(root)])
    json.loads(capsys.readouterr().out)

    assert not marker.exists()


def test_inherited_repository_variables_do_not_redirect_a_read_of_a_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` pointing at repository B, the head
    commit read of repository A is still A's."""

    from outcomebound_tools import tickets_git
    from outcomebound_tools.gitenv import git_environment

    def commit(folder: Path, message: str) -> str:
        folder.mkdir()
        for arguments in (
            ["init", "-q"],
            [
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@t",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                message,
            ],
            ["rev-parse", "HEAD"],
        ):
            done = subprocess.run(
                ["git", *arguments], cwd=folder, capture_output=True, text=True, check=True
            )
        return done.stdout.strip()

    first = commit(tmp_path / "a", "first")
    second = commit(tmp_path / "b", "second")
    assert first != second
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "b" / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "b"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "b" / ".git" / "index"))
    assert tickets_git.head_commit(tmp_path / "a") == first
    composed = git_environment()
    assert not {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"} & composed.keys()
