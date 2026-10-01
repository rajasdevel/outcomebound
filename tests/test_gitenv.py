"""Every Git subprocess in the engine runs under the C locale.

The engine reads Git's own messages, and a non-English locale rewrites them. One
helper composes the child environment, and this node holds every call site to it.
"""

from __future__ import annotations

import ast
from pathlib import Path

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
