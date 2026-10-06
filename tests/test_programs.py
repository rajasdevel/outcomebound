"""`programs`: finding a program on PATH and stopping the tree it started.

The Windows branch runs here beside scratch folders (`windows=True`, a `PATHEXT` and a folder
laid out as Git for Windows lays it out); what only a Windows process shows, that `taskkill`
ends a real tree and that `sh.exe` runs a line, is settled by the Windows CI job, which runs
`tests/test_finish_check.py` and the floor's tests against the real thing.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import programs
from tests.portable import WINDOWS
from tests.processes import running

# In lower case, so that the files laid out below are found on a case-sensitive file system too.
PATHEXT = ".com;.exe;.bat;.cmd"


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    path.chmod(0o755)
    return path


def search(*folders: Path, pathext: str = PATHEXT) -> dict[str, str]:
    return {"PATH": os.pathsep.join(str(folder) for folder in folders), "PATHEXT": pathext}


# The POSIX branch of `find` is `shutil.which`'s, whose lookup on Windows is another one: it reads
# PATHEXT, and a file with no extension is no program. The Windows branch is the `windows=True`
# tests below, which run on every platform.
posix_lookup = pytest.mark.skipif(
    WINDOWS, reason="the POSIX branch of find is shutil.which's, which on Windows reads PATHEXT"
)


@posix_lookup
def test_a_program_is_found_in_the_first_absolute_entry_that_holds_it(tmp_path: Path) -> None:
    """Breaks if a later entry answers before an earlier one, or if the lookup differs from
    `shutil.which` on POSIX."""

    first, second = touch(tmp_path / "a/tool"), touch(tmp_path / "b/tool")
    assert programs.find("tool", search(first.parent, second.parent), windows=False) == str(first)
    assert programs.find("tool", search(second.parent, first.parent), windows=False) == str(second)
    assert programs.find("absent", search(first.parent), windows=False) is None


def test_the_current_folder_and_a_relative_entry_never_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a program the folder a command runs in holds, a target's own `git`, answers
    for the one on PATH: through an empty entry, a `.` entry, a relative entry, or, on Windows,
    with no entry at all, where `CreateProcess` looks in the current folder first."""

    touch(tmp_path / "tool")
    touch(tmp_path / "tool.exe")
    touch(tmp_path / "bin/tool")
    monkeypatch.chdir(tmp_path)
    for windows in (False, True):
        for path in ("", ".", f"{os.pathsep}.{os.pathsep}bin", "bin"):
            where = {"PATH": path, "PATHEXT": PATHEXT}
            assert programs.find("tool", where, windows=windows) is None, (windows, path)
    if not WINDOWS:
        # `shutil.which` on Windows looks in the current folder first, which holds a `tool` here,
        # so the answer would say nothing about the entry; the Windows branch is asked above.
        assert programs.find("tool", {"PATH": str(tmp_path / "bin")}, windows=False)


def test_a_name_with_a_folder_in_it_is_the_callers_own_path(tmp_path: Path) -> None:
    """Breaks if `./check` or `scripts/run` is looked up on PATH, or refused: the caller named
    the file."""

    assert programs.require("./check", search(tmp_path), windows=False) == "./check"
    assert programs.resolve(["scripts/run", "-x"], search(tmp_path), windows=False) == [
        "scripts/run",
        "-x",
    ]
    assert programs.find("scripts/run", search(tmp_path), windows=False) is None
    assert programs.require("scripts\\run", search(tmp_path), windows=True) == "scripts\\run"


def test_a_program_that_is_not_on_path_raises_the_error_every_caller_already_reads(
    tmp_path: Path,
) -> None:
    """Breaks if a missing program starts something else, or raises an error the callers of a
    process do not catch."""

    with pytest.raises(FileNotFoundError, match="nosuch is not on PATH"):
        programs.require("nosuch", search(tmp_path), windows=False)
    with pytest.raises(FileNotFoundError):
        programs.resolve(["nosuch", "a"], search(tmp_path), windows=False)


@posix_lookup
def test_posix_searches_the_default_path_only_where_the_environment_has_none() -> None:
    """Breaks if a child's environment with no PATH finds nothing, where `execvp` finds
    `/bin/sh`, or if an empty PATH finds anything."""

    assert programs.find("sh", {}, windows=False) is not None
    assert programs.find("sh", {"PATH": ""}, windows=False) is None


def test_windows_tries_each_pathext_extension_in_each_entry(tmp_path: Path) -> None:
    """Breaks if `npm` finds no `npm.cmd` (`CreateProcess` adds only `.exe`), if an extension
    wins over an earlier entry's, or if a file with no extension, which `CreateProcess` cannot
    run, is started."""

    cmd = touch(tmp_path / "node/npm.cmd")
    exe = touch(tmp_path / "later/npm.exe")
    bare = touch(tmp_path / "scripts/mytool")
    where = search(cmd.parent, exe.parent, bare.parent)
    assert programs.find("npm", where, windows=True) == str(cmd)
    assert programs.find("npm.cmd", where, windows=True) == str(cmd)
    assert programs.find("npm.exe", where, windows=True) == str(exe)
    assert programs.find("mytool", where, windows=True) is None
    assert programs.find("mytool", where, windows=True, extensionless=True) == str(bare)
    assert programs.find("npm", search(cmd.parent, pathext=".exe"), windows=True) is None


def test_windows_reads_path_and_pathext_in_any_case(tmp_path: Path) -> None:
    """Breaks if an environment copied as `{"Path": ...}` finds nothing, or a quoted entry."""

    exe = touch(tmp_path / "bin/tool.exe")
    assert programs.find("tool", {"Path": f'"{exe.parent}"', "pathext": ".exe"}, windows=True)


def test_the_windows_subsystem_for_linux_launcher_is_never_the_bash_found(tmp_path: Path) -> None:
    """Breaks if `bash` starts `System32\\bash.exe`, which says "no installed distributions"
    where none is installed: the floor would read that as a syntax failure of every script."""

    stub = touch(tmp_path / "Windows/System32/bash.exe")
    alias = touch(tmp_path / "Users/me/AppData/Local/Microsoft/WindowsApps/bash.exe")
    real = touch(tmp_path / "Git/usr/bin/bash.exe")
    assert programs.find("bash", search(stub.parent, alias.parent, real.parent), windows=True) == (
        str(real)
    )
    assert programs.find("bash", search(stub.parent, alias.parent), windows=True) is None
    assert programs.stub_found("bash", search(stub.parent), windows=True) == str(stub)
    assert programs.stub_found("bash", search(real.parent), windows=True) is None
    # A tool of the same folder that is no launcher is found.
    tar = touch(tmp_path / "Windows/System32/tar.exe")
    assert programs.find("tar", search(tar.parent), windows=True) == str(tar)
    assert programs.stub_found("bash", search(stub.parent), windows=False) is None


def test_a_store_alias_is_never_the_python_found(tmp_path: Path) -> None:
    """Breaks if `python` starts the Microsoft Store alias, which opens the Store and runs no
    Python."""

    alias = touch(tmp_path / "AppData/Local/Microsoft/WindowsApps/python.exe")
    real = touch(tmp_path / "Python313/python.exe")
    assert programs.find("python", search(alias.parent, real.parent), windows=True) == str(real)
    assert programs.find("python", search(alias.parent), windows=True) is None
    other = touch(alias.parent / "winget.exe")
    assert programs.find("winget", search(alias.parent), windows=True) == str(other)


def test_bash_and_sh_come_from_git_for_windows_where_path_holds_only_its_git(
    tmp_path: Path,
) -> None:
    """Breaks if a machine whose PATH holds `Git\\cmd` (the default install) has no shell, or
    gets the stub's: the shell is `bin\\sh.exe` of the installation `git.exe` sits in, whichever
    of its three folders `git.exe` is on PATH from."""

    stub = touch(tmp_path / "Windows/System32/bash.exe")
    for layout, git in {
        "cmd": "cmd/git.exe",
        "bin": "bin/git.exe",
        "mingw": "mingw64/bin/git.exe",
    }.items():
        root = tmp_path / layout / "Git"
        touch(root / git)
        sh, bash = touch(root / "bin/sh.exe"), touch(root / "bin/bash.exe")
        where = search(stub.parent, (root / git).parent)
        assert programs.posix_shell(where, windows=True) == str(sh), layout
        assert programs.command("bash", where, windows=True) == [str(bash)], layout
    nowhere = search(stub.parent)
    assert programs.posix_shell(nowhere, windows=True) is None
    assert programs.command("bash", nowhere, windows=True) is None


def test_a_shell_on_path_wins_over_the_one_beside_git(tmp_path: Path) -> None:
    """Breaks if the shell beside `git` is taken before the one a person put on PATH."""

    touch(tmp_path / "Git/cmd/git.exe")
    touch(tmp_path / "Git/bin/sh.exe")
    mine = touch(tmp_path / "msys/sh.exe")
    where = search(tmp_path / "Git/cmd", mine.parent)
    assert programs.posix_shell(where, windows=True) == str(mine)


def test_windows_has_python_where_it_has_no_python3(tmp_path: Path) -> None:
    """Breaks if a claim or `provision` that names `python3` finds nothing on a machine whose
    Python is `python.exe` or only the `py` launcher, or starts `py` without `-3`."""

    alias = touch(tmp_path / "WindowsApps/python3.exe")
    python = touch(tmp_path / "Python/python.exe")
    launcher = touch(tmp_path / "Windows/py.exe")
    assert programs.command("python3", search(alias.parent, python.parent), windows=True) == [
        str(python)
    ]
    assert programs.command("python3", search(alias.parent, launcher.parent), windows=True) == [
        str(launcher),
        "-3",
    ]
    assert programs.command("python3", search(alias.parent), windows=True) is None
    real3 = touch(tmp_path / "other/python3.exe")
    assert programs.command("python3", search(real3.parent, python.parent), windows=True) == [
        str(real3)
    ]
    assert programs.resolve(["python3", "-m", "pytest"], search(python.parent), windows=True) == [
        str(python),
        "-m",
        "pytest",
    ]
    # Off Windows `python3` is only itself.
    assert programs.command("python3", search(python.parent), windows=False) is None


def test_the_shells_own_tools_go_last_on_windows_path(tmp_path: Path) -> None:
    """Breaks if `cat` and `sleep` of a Done line are not found by a shell started from outside
    Git Bash, or if the shell's folder displaces a tool already on PATH, or is added twice."""

    sh = touch(tmp_path / "Git/bin/sh.exe")
    tools = tmp_path / "Git/usr/bin"
    tools.mkdir(parents=True)
    mine = tmp_path / "mine"
    one = programs.shell_environment(
        str(sh), {"Path": f"{mine}{os.pathsep}", "HOME": "h"}, windows=True
    )
    assert one is not None
    assert one["Path"] == f"{mine}{os.pathsep}{tools}" and one["HOME"] == "h"
    two = programs.shell_environment(str(sh), one, windows=True)
    assert two is not None and two["Path"] == one["Path"]
    direct = touch(tools / "sh.exe")
    three = programs.shell_environment(str(direct), {"PATH": "x"}, windows=True)
    assert three is not None and three["PATH"] == f"x{os.pathsep}{tools}"
    bare = touch(tmp_path / "Elsewhere/bin/sh.exe")
    assert programs.shell_environment(str(bare), {"PATH": "x"}, windows=True) == {"PATH": "x"}


def test_the_environment_is_left_as_it_is_off_windows() -> None:
    """Breaks if a POSIX run's environment is changed."""

    assert programs.shell_environment("/bin/sh", None, windows=False) is None
    assert programs.shell_environment("/bin/sh", {"PATH": "x"}, windows=False) == {"PATH": "x"}


def test_a_group_is_a_new_session_on_posix_and_a_new_process_group_on_windows() -> None:
    """Breaks if Windows gets a keyword it ignores, so that Ctrl-C reaches the command and a
    stop reaches the engine's own group, or if POSIX loses its session."""

    assert programs.new_group(windows=False) == {"start_new_session": True}
    flags = programs.new_group(windows=True)["creationflags"]
    assert flags == 0x200


def test_windows_stops_a_tree_with_taskkill_by_path_and_kills_the_process_after_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the tree is left running (no `/T`), if `taskkill` is found through the current
    folder, which a target can fill, or if a `taskkill` that cannot run leaves the process
    alive: here it cannot, and the process is killed in its place."""

    asked: list[list[str]] = []

    def cannot(argv: list[str], **options: Any) -> None:
        asked.append(argv)
        assert options["timeout"] == programs.TASKKILL_SECONDS
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(programs.subprocess, "run", cannot)
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path / "Windows"))
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        programs.stop_tree(process, windows=True)
        assert process.wait(timeout=30) != 0
    finally:
        process.kill()
        process.wait()
    assert asked == [
        [
            str(tmp_path / "Windows" / "System32" / "taskkill.exe"),
            "/T",
            "/F",
            "/PID",
            str(process.pid),
        ]
    ]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups; Windows is the test above")
def test_a_posix_stop_ends_the_command_and_everything_it_started(tmp_path: Path) -> None:
    """Breaks if only the direct child is killed: the grandchild keeps the pipe open and keeps
    running."""

    pid = tmp_path / "pid"
    line = f"sleep 60 & echo $! > {pid}; wait"
    process = subprocess.Popen(["/bin/sh", "-c", line], **programs.new_group())
    deadline = time.monotonic() + 30
    while not (pid.exists() and pid.read_text(encoding="utf-8").strip()):
        assert time.monotonic() < deadline, "the command never wrote its pid"
        time.sleep(0.01)
    grandchild = int(pid.read_text(encoding="utf-8"))

    programs.stop_tree(process)

    assert process.wait(timeout=30) == -signal.SIGKILL
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and running(grandchild):
        time.sleep(0.1)
    alive = running(grandchild)
    if alive:
        with contextlib.suppress(ProcessLookupError):
            os.kill(grandchild, signal.SIGKILL)
    assert not alive, "the grandchild outlived its group"


def test_a_process_with_no_group_of_its_own_is_killed_alone_and_never_raises() -> None:
    """Breaks if a process that leads no group of its own, or one that has already ended, makes
    `stop_tree` raise, or if the first is left running."""

    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    programs.stop_tree(process)
    assert process.wait(timeout=30) != 0
    programs.stop_tree(process)
