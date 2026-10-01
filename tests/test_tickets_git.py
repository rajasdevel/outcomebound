"""The one seam every ticket module reaches git through, and the one process it starts.

Each test builds its own scratch repository under `tmp_path` and writes the
identity into that repository's own config, so a runner with no global git
identity — a CI container, a fresh machine — reads the same as any other.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Callable
from pathlib import Path

import pytest

from outcomebound_tools.tickets_git import (
    GitError,
    GitResult,
    git,
    head_commit,
    tree_clean,
)


def _git(root: Path, *arguments: str) -> GitResult:
    """A setup command that must have worked, with git's own message on failure."""

    outcome = git(root, *arguments)
    assert outcome.status == 0, outcome.stderr.decode("utf-8", "replace")
    return outcome


def _repository(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "tickets@example.invalid")
    _git(root, "config", "user.name", "Ticket Tests")
    _git(root, "config", "commit.gpgsign", "false")
    return root


def _commit(root: Path, message: str, **files: str) -> str:
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return head_commit(root)


# --- the call itself -------------------------------------------------------------


def test_a_failing_command_is_returned_and_not_raised(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    outcome = git(root, "rev-parse", "--verify", "refs/heads/nothing")
    assert outcome.status != 0
    assert outcome.stdout == b""
    assert isinstance(outcome.stderr, bytes) and outcome.stderr != b""


def test_output_that_is_not_utf8_decodes_with_replacement(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "latin1.txt").write_bytes(b"caf\xe9\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "a blob that is not utf-8")
    shown = git(root, "show", "HEAD:latin1.txt")
    assert shown.status == 0
    assert "�" in shown.text
    assert shown.stdout == b"caf\xe9\n"


def test_a_target_git_cannot_be_run_in_is_a_named_error(tmp_path: Path) -> None:
    with pytest.raises(GitError) as raised:
        git(tmp_path / "there-is-no-such-directory", "status")
    assert "there-is-no-such-directory" in str(raised.value)


# --- the two questions ------------------------------------------------------------


def test_head_commit_and_its_refusals(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitError) as outside:
        head_commit(plain)
    assert "plain" in str(outside.value)

    root = _repository(tmp_path)
    with pytest.raises(GitError):
        head_commit(root)

    commit = _commit(root, "first", answer="one\n")
    assert len(commit) == 40 and set(commit) <= set("0123456789abcdef")
    assert commit == _git(root, "rev-parse", "HEAD").text.strip()


def test_tree_clean_sees_untracked_and_staged(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    _commit(root, "first", answer="one\n")
    assert tree_clean(root) is True

    (root / "new.txt").write_text("untracked\n", encoding="utf-8")
    assert tree_clean(root) is False

    _git(root, "add", "new.txt")
    assert tree_clean(root) is False

    _git(root, "commit", "-q", "-m", "second")
    assert tree_clean(root) is True

    (root / "answer").write_text("changed\n", encoding="utf-8")
    assert tree_clean(root) is False


# --- what the engine may reach at all ---------------------------------------------


ENGINE_FILES = sorted(
    (Path(__file__).resolve().parent.parent / "outcomebound_tools").glob("tickets*.py")
)
# The one ticket module that may start a process.
GIT_SEAM = "tickets_git.py"
# Every standard-library way to start a process, not `subprocess` alone: a
# module that imports one of these has opened a second way to run something,
# whatever it then does with it.
SPAWNING_MODULES = frozenset({"subprocess", "pty", "multiprocessing", "asyncio"})
# The names on `os` that start a process. `system` and `popen` are exact; the
# `exec` and `spawn` families are whole families, and no other `os` attribute
# begins with either word.
SPAWNING_OS_NAMES = frozenset({"system", "popen"})
SPAWNING_OS_FAMILIES = ("exec", "spawn")
# What `validation` offers that runs a command: the engine names a claim's command
# and runs none.
RUNNERS = frozenset({"run_claim", "run_plan", "_execute"})
NETWORK_MODULES = frozenset(
    {
        "ftplib",
        "http",
        "imaplib",
        "nntplib",
        "poplib",
        "requests",
        "smtplib",
        "socket",
        "socketserver",
        "ssl",
        "telnetlib",
        "urllib",
        "urllib3",
        "webbrowser",
        "xmlrpc",
    }
)


def _trees() -> dict[str, ast.Module]:
    return {
        path.name: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in ENGINE_FILES
    }


def _imported(tree: ast.Module) -> set[str]:
    """Every module this file imports: the top-level name, and the engine's own."""

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            found.add(node.module.split(".")[0])
            if node.module == "outcomebound_tools":
                found.update(alias.name for alias in node.names)
    return found


def _starts_a_process(name: str) -> bool:
    """Whether a name taken off `os` starts a process."""

    return name in SPAWNING_OS_NAMES or name.startswith(SPAWNING_OS_FAMILIES)


def _taken(tree: ast.Module, module: str, wanted: Callable[[str], bool]) -> set[str]:
    """Every `<module>.<name>` this file reaches that `wanted` picks, by either spelling:
    as an attribute of the module, or imported out of it by name."""

    found: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == module
            and wanted(node.attr)
        ):
            found.add(f"{module}.{node.attr}")
        elif isinstance(node, ast.ImportFrom) and node.module in (
            module,
            f"outcomebound_tools.{module}",
        ):
            found.update(f"{module}.{alias.name}" for alias in node.names if wanted(alias.name))
    return found


def test_the_ticket_engine_runs_only_git() -> None:
    """The ticket engine's one way to start a process is `git`, through this seam, and
    it runs no claim.

    The whole ticket surface is surveyed, so every `outcomebound_tools/tickets*.py`
    the glob finds answers for itself and a module added later is surveyed by having
    been written. Two spellings are looked for, because a boundary drawn around one
    import name is not a boundary: a module may reach a process through `subprocess`,
    `pty`, `multiprocessing` or `asyncio`, or through a name taken off `os`, which
    every module imports for ordinary reasons.
    """

    trees = _trees()
    assert GIT_SEAM in trees, f"the survey is missing {GIT_SEAM}: {sorted(trees)}"

    spawning = {name for name, tree in trees.items() if _imported(tree) & SPAWNING_MODULES}
    assert spawning == {GIT_SEAM}, f"the ticket engine's spawning modules are {sorted(spawning)}"
    reaching = {
        name: sorted(found)
        for name, tree in trees.items()
        if (
            found := _taken(tree, "os", _starts_a_process)
            | _taken(tree, "validation", RUNNERS.__contains__)
        )
    }
    assert not reaching, f"ticket modules start a process or run a claim: {reaching}"

    for node in ast.walk(trees[GIT_SEAM]):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "subprocess":
            continue
        argv = node.args[0]
        assert isinstance(argv, ast.List) and argv.elts, "a git call with no argv list"
        first = argv.elts[0]
        assert isinstance(first, ast.Constant) and first.value == "git", ast.dump(first)


def test_the_ticket_engine_opens_no_network() -> None:
    """No socket, URL, HTTP or TLS module is reachable from the engine."""

    for name, tree in _trees().items():
        reached = _imported(tree) & NETWORK_MODULES
        assert reached == set(), f"{name} imports {sorted(reached)}"


def test_tests_import_only_public_names() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__)
    reached = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if not node.module.startswith("outcomebound_tools.tickets"):
            continue
        public = set(importlib.import_module(node.module).__all__)
        for alias in node.names:
            reached += 1
            assert alias.name in public, f"{node.module}.{alias.name} is not in __all__"
    assert reached == 5, "this file imports exactly the seam it tests"
