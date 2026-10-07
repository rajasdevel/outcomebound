"""Finding a program on PATH, and stopping the tree it started, the same way on every platform.

What this module decides: which file a program name means, and what stops a process and everything
it started. A name is looked for in PATH's absolute entries only, in order, so neither the current
folder nor a folder the target supplies can answer for it. On POSIX the lookup is `shutil.which`'s.
On Windows it tries each `PATHEXT` extension in each entry, which `CreateProcess` does not do for
`.cmd` and `.bat`, and it skips two kinds of stub: `bash` in `System32` or `WindowsApps` is the
launcher of the Windows Subsystem for Linux, which reads "no installed distributions" where none
is installed, and `python` or `python3` in `WindowsApps` is an app execution alias that opens the
Store. A POSIX shell on Windows is the `sh.exe` of Git for Windows, found on PATH or beside `git`.
A process group is a new session on POSIX and `CREATE_NEW_PROCESS_GROUP` on Windows; its tree is
stopped by `killpg` on POSIX and `taskkill /T /F` on Windows.

What it does not decide: whether a program is the right one, or what a caller does where none is
found. `require` raises `FileNotFoundError`, which every caller of a process already reads.

`windows=` and `environment=` exist so that a test can run the Windows branch beside a scratch
folder on any platform.
"""

from __future__ import annotations

import contextlib
import errno
import os
import shutil
import signal
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path, PureWindowsPath
from typing import Any

__all__ = [
    "command",
    "environment_value",
    "find",
    "new_group",
    "posix_shell",
    "require",
    "resolve",
    "shell_environment",
    "stop_tree",
    "stub",
    "stub_found",
]

DEFAULT_PATHEXT = (".COM", ".EXE", ".BAT", ".CMD")
# Folders whose `bash` is the Windows Subsystem for Linux launcher, and the one folder whose
# `python` is an app execution alias.
LAUNCHER_FOLDERS = frozenset({"system32", "syswow64", "sysnative", "windowsapps"})
ALIAS_FOLDERS = frozenset({"windowsapps"})
LAUNCHER_PROGRAMS = frozenset({"bash", "sh"})
ALIAS_PROGRAMS = frozenset({"python", "python3"})
# How long `taskkill` may take before the process alone is killed.
TASKKILL_SECONDS = 10


def _windows(windows: bool | None) -> bool:
    return os.name == "nt" if windows is None else windows


def _variable(environment: Mapping[str, str] | None, name: str, windows: bool) -> str | None:
    """`name` in `environment` (this process's by default); on Windows its case does not matter,
    though a dict copied from the environment may hold it as `Path`."""

    source = os.environ if environment is None else environment
    if name in source:
        return source[name]
    if windows:
        for key, value in source.items():
            if key.upper() == name:
                return value
    return None


def environment_value(
    environment: Mapping[str, str] | None, name: str, *, windows: bool | None = None
) -> str | None:
    """Read an environment variable, including a Windows Mapping with mixed-case keys."""

    return _variable(environment, name, _windows(windows))


def _entries(environment: Mapping[str, str] | None, windows: bool) -> list[str]:
    """PATH's absolute entries, in order. A PATH the environment does not hold at all is the
    default `execvp` uses on POSIX; an empty one holds nothing."""

    raw = _variable(environment, "PATH", windows)
    if raw is None:
        raw = "" if windows else os.defpath
    parts = (part.strip('"') if windows else part for part in raw.split(os.pathsep))
    return [part for part in parts if part and os.path.isabs(part)]


def _has_separator(name: str, windows: bool) -> bool:
    return "/" in name or (windows and "\\" in name)


def stub(path: str | os.PathLike[str]) -> bool:
    """Whether a file at `path` is a Windows stub that is no use as the program its name says:
    the Windows Subsystem for Linux launcher, or a Store alias for Python. Decided from the
    folder and the name, so it holds on any platform."""

    place = PureWindowsPath(path)
    folder, program = place.parent.name.casefold(), place.stem.casefold()
    return (program in LAUNCHER_PROGRAMS and folder in LAUNCHER_FOLDERS) or (
        program in ALIAS_PROGRAMS and folder in ALIAS_FOLDERS
    )


def _candidates(name: str, environment: Mapping[str, str] | None, extensionless: bool) -> list[str]:
    """The file names a Windows lookup tries in each entry: the name itself where it already
    ends in a `PATHEXT` extension, else the name with each; a bare name last where asked."""

    text = _variable(environment, "PATHEXT", True)
    extensions = [part for part in (text or "").split(";") if part] or list(DEFAULT_PATHEXT)
    known = {extension.casefold() for extension in extensions}
    if os.path.splitext(name)[1].casefold() in known:
        names = [name]
    else:
        names = [name + extension for extension in extensions]
    return [*names, name] if extensionless and name not in names else names


def find(
    name: str,
    environment: Mapping[str, str] | None = None,
    *,
    windows: bool | None = None,
    extensionless: bool = False,
) -> str | None:
    """The absolute path of the program a bare `name` means, or None.

    `extensionless` also accepts a file with no extension on Windows, which a POSIX shell there
    runs where it holds a script and `CreateProcess` does not: for asking what a shell could
    find, never for starting a program."""

    windows = _windows(windows)
    if not name or _has_separator(name, windows):
        return None
    entries = _entries(environment, windows)
    if not windows:
        return shutil.which(name, path=os.pathsep.join(entries)) if entries else None
    names = _candidates(name, environment, extensionless)
    for entry in entries:
        for each in names:
            candidate = os.path.join(entry, each)
            if os.path.isfile(candidate) and not stub(candidate):
                return candidate
    return None


def _stub_only(name: str, environment: Mapping[str, str] | None) -> str | None:
    """On Windows, the first stub a lookup of `name` skipped, else None."""

    for entry in _entries(environment, True):
        for each in _candidates(name, environment, False):
            candidate = os.path.join(entry, each)
            if os.path.isfile(candidate) and stub(candidate):
                return candidate
    return None


def _git_program(name: str, environment: Mapping[str, str] | None, windows: bool) -> str | None:
    """The `name.exe` of Git for Windows, found from the `git` on PATH: its folder is `cmd`,
    `bin` or `mingw64\\bin` of an installation whose own `bin` and `usr\\bin` hold the shell."""

    git = find("git", environment, windows=windows)
    if git is None:
        return None
    for parent in Path(git).parents[:3]:
        for relative in ("bin", os.path.join("usr", "bin")):
            candidate = parent / relative / f"{name}.exe"
            if candidate.is_file():
                return str(candidate)
    return None


def command(
    name: str, environment: Mapping[str, str] | None = None, *, windows: bool | None = None
) -> list[str] | None:
    """What starts the program a bare `name` means, as the words that go before its arguments, or
    None where there is none: `[path]`, or on Windows, where `python3` is often not installed,
    `python3`'s stand-in `python`, else `[py, "-3"]`, and `bash` from Git for Windows where PATH
    holds only the stub."""

    windows = _windows(windows)
    found = find(name, environment, windows=windows)
    if found is not None:
        return [found]
    if not windows:
        return None
    if name == "python3":
        python = find("python", environment, windows=True)
        if python is not None:
            return [python]
        launcher = find("py", environment, windows=True)
        return None if launcher is None else [launcher, "-3"]
    if name in LAUNCHER_PROGRAMS:
        shell = _git_program(name, environment, True)
        return None if shell is None else [shell]
    return None


def require(
    name: str, environment: Mapping[str, str] | None = None, *, windows: bool | None = None
) -> str:
    """The program `name` means, as the first word of an argv; a name with a folder in it is
    the caller's own path and stays as given. Raises `FileNotFoundError` where PATH has none."""

    if _has_separator(name, _windows(windows)):
        return name
    found = find(name, environment, windows=windows)
    if found is None:
        raise FileNotFoundError(errno.ENOENT, f"{name} is not on PATH")
    return found


def resolve(
    argv: Sequence[str],
    environment: Mapping[str, str] | None = None,
    *,
    windows: bool | None = None,
) -> list[str]:
    """`argv` with its first word found on PATH, as `command` finds it; a first word with a
    folder in it stays as given. Raises `FileNotFoundError` where PATH has none."""

    first, rest = argv[0], list(argv[1:])
    if _has_separator(first, _windows(windows)):
        return list(argv)
    start = command(first, environment, windows=windows)
    if start is None:
        raise FileNotFoundError(errno.ENOENT, f"{first} is not on PATH")
    return [*start, *rest]


def stub_found(
    name: str, environment: Mapping[str, str] | None = None, *, windows: bool | None = None
) -> str | None:
    """On Windows, the stub that stands where `name` is not found (the Windows Subsystem for Linux
    launcher for `bash`, a Store alias for `python`), so a reason can name it; else None."""

    return _stub_only(name, environment) if _windows(windows) else None


def posix_shell(
    environment: Mapping[str, str] | None = None, *, windows: bool | None = None
) -> str | None:
    """The shell that runs a Done line: `/bin/sh` where there is one; on Windows the `sh.exe` PATH
    holds or Git for Windows has beside its `git`; else None."""

    windows = _windows(windows)
    if not windows:
        return "/bin/sh" if os.path.exists("/bin/sh") else find("sh", environment, windows=False)
    return find("sh", environment, windows=True) or _git_program("sh", environment, True)


def shell_environment(
    shell: str, environment: Mapping[str, str] | None = None, *, windows: bool | None = None
) -> dict[str, str] | None:
    """The environment a line runs in under `shell`: on Windows, the shell's own `usr\\bin` last on
    PATH where PATH lacks it, so that the POSIX tools a line names (`cat`, `sleep`) are found; a
    tool PATH already holds wins. Elsewhere `environment` as given, None for this process's."""

    if not _windows(windows):
        return None if environment is None else dict(environment)
    composed = dict(os.environ if environment is None else environment)
    place = Path(shell).parent
    tools = place if place.parent.name.casefold() == "usr" else place.parent / "usr" / "bin"
    if not tools.is_dir():
        return composed
    key = next((key for key in composed if key.upper() == "PATH"), "PATH")
    entries = [entry for entry in composed.get(key, "").split(os.pathsep) if entry]
    if os.path.normcase(os.path.normpath(tools)) not in {
        os.path.normcase(os.path.normpath(entry)) for entry in entries
    }:
        composed[key] = os.pathsep.join([*entries, str(tools)])
    return composed


def new_group(*, windows: bool | None = None) -> dict[str, Any]:
    """The `Popen` keywords that make a child lead its own process group: a new session on POSIX,
    where the terminal's Ctrl-C then never reaches it, and `CREATE_NEW_PROCESS_GROUP` on
    Windows."""

    if _windows(windows):
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)}
    return {"start_new_session": True}


def _taskkill() -> str:
    """`taskkill` in the system folder, named by its path: `CreateProcess` looks in the current
    folder before it, which a target can hold."""

    root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or r"C:\Windows"
    return os.path.join(root, "System32", "taskkill.exe")


def stop_tree(process: subprocess.Popen[bytes], *, windows: bool | None = None) -> None:
    """Kill the process and everything it started, and never raise. A process that did not start
    with `new_group` has no group of its own on POSIX; then only it is killed. On Windows
    `taskkill /T /F` ends the tree, and the process is killed after it where taskkill could not
    run."""

    if _windows(windows):
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                [_taskkill(), "/T", "/F", "/PID", str(process.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=TASKKILL_SECONDS,
                check=False,
            )
    else:
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
            return
    with contextlib.suppress(OSError):
        process.kill()
