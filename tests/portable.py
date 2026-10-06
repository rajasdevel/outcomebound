"""What a test needs to run on every platform the product supports: Windows, macOS, Linux and
containers (Debian as root, Alpine with no bash). A test that needs a feature a platform lacks
skips with the reason, and `-rs` prints it, so a skip is never read as a pass."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path, PurePath, PureWindowsPath

import pytest

ROOT = Path(__file__).resolve().parent.parent
WINDOWS = os.name == "nt"
ROOT_USER = hasattr(os, "geteuid") and os.geteuid() == 0

# `scripts/outcomebound`'s own run of a checkout, under this Python: the engine as a test
# starts it, on every platform, where the sh launcher itself is a POSIX file.
LAUNCH = """import runpy, sys
sys.path.insert(0, sys.argv[1])
sys.argv = ["outcomebound", *sys.argv[2:]]
runpy.run_module("outcomebound_tools", run_name="__main__", alter_sys=True)
"""


def engine(*arguments: str | Path) -> list[str]:
    """The command line that runs this checkout's engine, isolated as the launcher runs it."""

    return [sys.executable, "-I", "-c", LAUNCH, str(ROOT), *map(str, arguments)]


def home_environment(home: PurePath, windows: bool = WINDOWS) -> dict[str, str]:
    """The variables that name a home: `HOME` for POSIX and Git, `USERPROFILE` for
    `Path.home()` on Windows, and there `HOMEDRIVE` and `HOMEPATH` too."""

    names = {"HOME": str(home), "USERPROFILE": str(home)}
    if windows:
        drive = PureWindowsPath(home).drive
        names["HOMEDRIVE"] = drive
        names["HOMEPATH"] = str(home)[len(drive) :]
    return names


def _usable_windows_bash(path: str, environ: Mapping[str, str]) -> bool:
    """False for the WSL stub: `bash.exe` in the Windows folder, or an app-execution alias."""

    folded = str(PureWindowsPath(path)).lower()
    windows = (environ.get("SystemRoot") or r"C:\Windows").lower().rstrip("\\")
    return not (folded.startswith(windows + "\\") or "\\windowsapps\\" in folded)


def windows_bash(
    which: Callable[[str], str | None],
    exists: Callable[[str], bool],
    environ: Mapping[str, str],
) -> str | None:
    """Git for Windows' bash: the one on PATH unless it is the WSL stub, else the one beside
    the `git` on PATH or in a standard install folder."""

    found = which("bash")
    if found and _usable_windows_bash(found, environ):
        return found
    folders = []
    git = which("git")
    if git:
        folders += list(PureWindowsPath(git).parents)
    for name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)", "LocalAppData"):
        if environ.get(name):
            folders.append(PureWindowsPath(environ[name]) / "Git")
    for folder in folders:
        for relative in ("bin", "usr\\bin"):
            candidate = str(folder / relative / "bash.exe")
            if _usable_windows_bash(candidate, environ) and exists(candidate):
                return candidate
    return None


def find_bash() -> str | None:
    """A real bash, or None where there is none (Alpine, a Windows with no Git for Windows)."""

    if WINDOWS:
        return windows_bash(shutil.which, os.path.isfile, os.environ)
    return shutil.which("bash")


BASH = find_bash()
NO_BASH = (
    "no bash: none on PATH (on Windows only Git for Windows' bash.exe counts, never the WSL "
    "stub in the Windows folder)"
)
needs_bash = pytest.mark.skipif(BASH is None, reason=NO_BASH)


def _eval_reason() -> str:
    if WINDOWS:
        return (
            "the eval fixtures, and the fake codex they run under, are POSIX shell scripts "
            "that maintainers run"
        )
    return NO_BASH if BASH is None else ""


EVAL_REASON = _eval_reason()
needs_posix_bash = pytest.mark.skipif(bool(EVAL_REASON), reason=EVAL_REASON or "-")
posix_only = pytest.mark.skipif(WINDOWS, reason="needs a POSIX feature Windows lacks")
not_root = pytest.mark.skipif(
    ROOT_USER, reason="the user is root, and root ignores file modes and read-only folders"
)


def run_bash(script: Path, *arguments: str | Path, **options) -> subprocess.CompletedProcess:
    """A bash script run with the bash `find_bash` found. A Windows path takes forward slashes,
    which bash.exe reads as it reads a POSIX path."""

    assert BASH is not None, NO_BASH
    words = [
        BASH,
        script.as_posix(),
        *(a.as_posix() if isinstance(a, Path) else a for a in arguments),
    ]
    return subprocess.run(words, **options)


def can_symlink() -> bool:
    """Whether this account can make a symbolic link: a Windows account without the privilege
    or Developer Mode cannot, though the runner's administrator account can."""

    with tempfile.TemporaryDirectory() as folder:
        try:
            (Path(folder) / "link").symlink_to(Path(folder), target_is_directory=True)
        except (OSError, NotImplementedError):
            return False
    return True


needs_symlinks = pytest.mark.skipif(
    not can_symlink(), reason="this account cannot make symbolic links"
)


def write(path: Path, text: str) -> None:
    """A fixture file as every platform writes it: UTF-8 and LF, never the platform's default
    encoding and line ending."""

    path.write_bytes(text.encode("utf-8"))


def process_alive(pid: int) -> bool:
    """Whether a POSIX process runs. A stopped child nobody has reaped is a zombie: `kill(pid, 0)`
    still finds it, as it does for every child in a container whose first process reaps none, so
    a zombie reads as gone. Not for Windows, where `os.kill(pid, 0)` would end the process."""

    assert not WINDOWS, "os.kill(pid, 0) ends a process on Windows"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rpartition(")")[2].split()[0]
    except (OSError, IndexError):
        done = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
        )
        state = done.stdout.strip()
    return not state.startswith("Z")
