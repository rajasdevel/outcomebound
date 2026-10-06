"""The test suite's own platform support: an isolated home that every platform's home lookup
reads, a bash that is never the WSL stub, and an engine start that needs no sh launcher."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path, PureWindowsPath

from tests.portable import ROOT, engine, home_environment, posix_only, process_alive, windows_bash

STUB = r"C:\Windows\System32\bash.exe"
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
WINDOWS_ENVIRONMENT = {"SystemRoot": r"C:\Windows", "ProgramFiles": r"C:\Program Files"}


def test_every_variable_that_names_a_home_names_the_isolated_one(isolated_home: Path) -> None:
    assert Path.home() == isolated_home
    assert Path(os.path.expanduser("~")) == isolated_home
    assert Path(os.environ["USERPROFILE"]) == isolated_home
    assert "CODEX_HOME" not in os.environ and "CLAUDE_CONFIG_DIR" not in os.environ


def test_each_test_gets_its_own_home(isolated_home: Path, session_home: Path) -> None:
    assert isolated_home != session_home
    assert not any(isolated_home.iterdir())


def test_a_windows_home_names_the_drive_and_the_path_apart() -> None:
    home = PureWindowsPath(r"D:\a\_temp\pytest\home0")

    assert home_environment(home, windows=True) == {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "HOMEDRIVE": "D:",
        "HOMEPATH": r"\a\_temp\pytest\home0",
    }
    assert set(home_environment(home, windows=False)) == {"HOME", "USERPROFILE"}


def _find(present: set[str], on_path: dict[str, str]):
    return windows_bash(on_path.get, lambda path: path in present, WINDOWS_ENVIRONMENT)


def test_the_wsl_stub_on_path_is_never_the_bash() -> None:
    assert _find(set(), {"bash": STUB}) is None
    windows_apps = r"C:\Users\p\AppData\Local\Microsoft\WindowsApps\bash.exe"
    assert _find(set(), {"bash": windows_apps}) is None


def test_git_for_windows_bash_is_found_beside_git_when_the_stub_comes_first() -> None:
    on_path = {"bash": STUB, "git": r"C:\Program Files\Git\cmd\git.exe"}

    assert _find({GIT_BASH}, on_path) == GIT_BASH


def test_git_for_windows_bash_is_found_in_its_standard_folder_with_no_git_on_path() -> None:
    assert _find({GIT_BASH}, {}) == GIT_BASH


def test_a_bash_on_path_that_is_not_the_stub_is_used() -> None:
    usable = r"C:\Program Files\Git\usr\bin\bash.exe"

    assert _find(set(), {"bash": usable}) == usable


def test_the_engine_starts_through_python_with_no_sh_launcher() -> None:
    done = subprocess.run(engine("home"), capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.strip()).resolve() == ROOT


@posix_only
def test_a_stopped_child_nobody_reaped_is_not_alive() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert process_alive(child.pid)
        child.kill()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and process_alive(child.pid):
            time.sleep(0.05)
        os.kill(child.pid, 0)  # the zombie is still in the table, as in a container
        assert not process_alive(child.pid)
    finally:
        child.kill()
        child.wait()
