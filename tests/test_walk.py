"""The engine's walks of a target: an unreadable folder stops no reader, a folder Git ignores
gives no byte-cap warning, and each `os.walk` in the package is one the allow-list names.

Every target is under `tmp_path`. A folder made unreadable gets its mode back at teardown, so
pytest can remove it.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from outcomebound_tools import adopt, instruction_audit

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git") or "git"
# The modules that may call `os.walk`: the one walk for the engine's readers, and two walks
# that keep their own rules: discovery's, with its entry and depth limits, and artifactcheck's
# walk of a specs folder, which passes over names that start with `_` or `.`.
WALKERS = {
    "outcomebound_tools/walk.py",
    "outcomebound_tools/discovery.py",
    "outcomebound_tools/artifactcheck.py",
}
Capture = pytest.CaptureFixture[str]

needs_permissions = pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="mode 000 keeps a folder unreadable only for a POSIX user that is not root",
)


def repo(path: Path, files: dict[str, str]) -> Path:
    """A Git repository at `path` holding `files` and one commit of them."""

    path.mkdir(parents=True)
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([GIT, "-C", str(path), "add", "-A"], check=True)
    subprocess.run([GIT, "-C", str(path), *identity, "commit", "-q", "-m", "c"], check=True)
    return path


@pytest.fixture
def lock() -> Iterator[Callable[[Path], None]]:
    """Make a folder unreadable, holding a `.git` as a nested repository would; each gets its
    mode back at teardown."""

    locked: list[Path] = []

    def make(folder: Path) -> None:
        (folder / ".git").mkdir(parents=True)
        folder.chmod(0)
        locked.append(folder)

    yield make
    for folder in reversed(locked):
        folder.chmod(0o755)


def adopt_run(capsys: Capture, *argv: str) -> tuple[int, str, str]:
    code = adopt.main(list(argv), source=ROOT)
    out, err = capsys.readouterr()
    return code, out, err


@needs_permissions
def test_an_unreadable_folder_stops_no_adopt_route(
    tmp_path: Path, capsys: Capture, lock: Callable[[Path], None]
) -> None:
    """A folder the user cannot read, holding a `.git`, is passed over by the install, its dry
    run and its check, on every Python the engine supports."""

    target = repo(tmp_path / "t", {"AGENTS.md": "# Project\n"})
    lock(target / "locked")

    for argv in (["--dry-run"], [], ["--check"]):
        harness = [] if argv == ["--check"] else ["--harness", "codex"]
        code, _, err = adopt_run(capsys, str(target), *harness, *argv)
        assert (code, err) == (0, ""), argv
    assert (target / ".outcomebound/manifest.json").is_file()


@needs_permissions
def test_instructions_check_reads_past_an_unreadable_folder(
    tmp_path: Path, lock: Callable[[Path], None]
) -> None:
    """Outside Git the whole target is walked, and an unreadable folder there is passed over;
    in a note folder it is listed itself, so it reads UNVERIFIED and no note is taken as read."""

    walked = tmp_path / "walked"
    walked.mkdir()
    (walked / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
    lock(walked / "locked")
    report = instruction_audit.check(walked, ["codex"])
    assert report.listed_by == "walk"
    assert "AGENTS.md" in {finding.path for finding in report.findings}

    listed = repo(tmp_path / "listed", {"AGENTS.md": "# Project\n"})
    (listed / ".agents/handoffs").mkdir(parents=True)
    lock(listed / ".agents/handoffs/old")
    report = instruction_audit.check(listed, ["codex"])
    assert report.listed_by == "git"
    verdicts = {f.verdict for f in report.findings if f.path == ".agents/handoffs/old"}
    assert verdicts == {"UNVERIFIED"}


def test_a_folder_git_ignores_gives_no_byte_cap_warning(tmp_path: Path, capsys: Capture) -> None:
    """A scratch copy of the project in an ignored folder is no part of what another clone
    gets, so its AGENTS.md past the cap is not measured; a tracked one past it still warns."""

    cap = adopt.harness_table(ROOT)["codex"]["doc_byte_cap"]
    target = repo(
        tmp_path / "t",
        {
            ".gitignore": ".agents/work/\n",
            "AGENTS.md": "# Project\n",
            "big/AGENTS.md": "b" * cap,
        },
    )
    copy = target / ".agents/work/copy/AGENTS.md"
    copy.parent.mkdir(parents=True)
    copy.write_text("c" * cap, encoding="utf-8")

    code, out, _ = adopt_run(capsys, str(target), "--harness", "codex")

    assert code == 0
    warned = [line for line in out.splitlines() if line.startswith("warning")]
    assert [line.split("a session in ")[1].split("/ ")[0] for line in warned] == ["big"]


def _os_walk_calls(tree: ast.AST) -> int:
    """Calls of `os.walk`, and imports of `walk` from `os`, in one module."""

    found = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            value = node.func.value
            found += node.func.attr == "walk" and isinstance(value, ast.Name) and value.id == "os"
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            found += any(alias.name == "walk" for alias in node.names)
    return found


def test_os_walk_appears_only_in_the_modules_the_allow_list_names() -> None:
    """A new walk of a target goes through `outcomebound_tools.walk`, or changes this list."""

    modules = sorted([*ROOT.glob("outcomebound_tools/*.py"), *ROOT.glob("scripts/*.py")])
    walkers = {
        path.relative_to(ROOT).as_posix()
        for path in modules
        if _os_walk_calls(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    }
    assert walkers == WALKERS
