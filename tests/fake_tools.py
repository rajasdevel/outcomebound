"""Stand-in tools for tests that start programs: one written source, found and run on every
platform the product supports.

A fake tool is a POSIX shell script. On POSIX the file is the tool. On Windows `CreateProcess`
runs no extension-less file, so the same script gets a `.cmd` beside it that runs it with the
POSIX shell the engine itself uses (`programs.posix_shell`): a lookup through `PATHEXT` finds
the `.cmd`, which is how a real tool installed by npm or pip is found there too. A test that
needs such a tool skips, with the reason, where Windows has no POSIX shell.
"""

from __future__ import annotations

import sys
from pathlib import Path, PureWindowsPath

import pytest

from outcomebound_tools import programs
from tests.portable import WINDOWS, write

NO_SHELL = (
    "no POSIX shell to run a stand-in tool: put the sh.exe of Git for Windows on PATH, or "
    "install Git for Windows"
)


def msys_path(path: Path) -> str:
    """`path` as an MSYS shell writes a folder inside a PATH list: `/d/work/tools` for
    `D:\\work\\tools`, which a list separated by `:` can hold where the drive's own colon cannot.
    Elsewhere the path as it is."""

    if not WINDOWS:
        return path.as_posix()
    place = PureWindowsPath(path)
    drive = place.drive.rstrip(":").lower()
    return "/".join(["", drive, *place.parts[1:]])


def _wrapper(shell: str, script: Path) -> bytes:
    """The `.cmd` that runs `script` with `shell`: the shell's own tools (`dirname`, `find`,
    `sort`) ahead of PATH, so that Windows' `find.exe` and `sort.exe` do not answer for them, the
    script named with forward slashes so that its `$0` is a path the shell reads, and the shell's
    exit code as the file's."""

    environment = programs.shell_environment(shell, {"PATH": ""}, windows=True) or {}
    tools = environment.get("PATH", "")
    lines = [
        "@echo off",
        f'set "PATH={tools};%PATH%"',
        f'"{shell}" "{script.as_posix()}" %*',
        "exit /b %ERRORLEVEL%",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def found(directory: Path, name: str) -> Path:
    """The file a lookup of `name` through `directory` alone finds."""

    path = programs.find(name, {"PATH": str(directory)})
    assert path is not None, f"{name} is not found in {directory}"
    return Path(path)


def shell_tool(directory: Path, name: str, script: str) -> Path:
    """A tool `name` in `directory` that runs the POSIX shell script `script`, as LF text. The
    file a PATH that holds `directory` finds is returned."""

    directory.mkdir(parents=True, exist_ok=True)
    body = directory / name
    write(body, script)
    body.chmod(0o755)
    if WINDOWS:
        shell = programs.posix_shell()
        if shell is None:
            pytest.skip(NO_SHELL)
        (directory / f"{name}.cmd").write_bytes(_wrapper(shell, body))
    return found(directory, name)


def python_tool(directory: Path, name: str) -> Path:
    """A tool `name` in `directory` that runs this interpreter with its arguments: a link on
    POSIX, a `.cmd` on Windows, where a copy of `python.exe` outside its installation does not
    run."""

    directory.mkdir(parents=True, exist_ok=True)
    if WINDOWS:
        text = f'@echo off\r\n"{sys.executable}" %*\r\nexit /b %ERRORLEVEL%\r\n'
        (directory / f"{name}.cmd").write_bytes(text.encode("utf-8"))
    else:
        (directory / name).symlink_to(sys.executable)
    return found(directory, name)
