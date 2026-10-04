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
        if isinstance(argv, ast.List) and argv.elts:
            first = argv.elts[0]
            if isinstance(first, ast.Constant) and first.value == "git":
                found.append(node)
    return found


def _environment_keyword(call: ast.Call) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == "env"), None)


def test_every_git_subprocess_runs_under_the_git_environment() -> None:
    """Each `subprocess.run(["git", …])` in the engine passes `env=git_environment(…)`,
    and none runs git through a shell."""

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


def test_the_read_prefix_stands_in_every_git_read_of_a_target() -> None:
    """The five readers of a target's Git state run under the same argv prefix."""

    readers = ("tickets_git", "harness_roots", "finish_check", "floor", "instruction_audit")
    for name in readers:
        source = (ROOT / "outcomebound_tools" / f"{name}.py").read_text(encoding="utf-8")
        assert "*GIT_READ_CONFIGURATION" in source, name


def _hostile_repository(tmp_path: Path) -> tuple[Path, Path]:
    """A repository whose own `.git/config` names a `core.fsmonitor` program that leaves a
    marker when it runs."""

    root = tmp_path / "target"
    (root / ".claude" / "skills" / "mine").mkdir(parents=True)
    (root / ".claude" / "skills" / "mine" / "SKILL.md").write_text("x\n", encoding="utf-8")
    marker = tmp_path / "fsmonitor-ran"
    hook = tmp_path / "hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    hook.chmod(0o755)
    commands = (
        ["init", "-q", "."],
        ["add", "-A"],
        ["-c", "user.email=a@example.org", "-c", "user.name=a", "commit", "-qm", "i"],
        ["config", "core.fsmonitor", str(hook)],
    )
    for arguments in commands:
        subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True)
    return root, marker


def test_no_read_of_a_target_runs_the_fsmonitor_program_its_git_config_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from outcomebound_tools import discovery, finish_check, floor, harness_roots, tickets_git

    root, marker = _hostile_repository(tmp_path)
    # Control: plain Git runs the program, so each check below can fail.
    subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True)
    assert marker.exists()
    marker.unlink()

    tickets_git.git(root, "status", "--porcelain")
    harness_roots._tracked(root, ".claude")
    finish_check._git(root, "status", "--porcelain")
    floor._git(root, "status", "--porcelain")
    discovery.main([str(root)])
    json.loads(capsys.readouterr().out)

    assert not marker.exists()
