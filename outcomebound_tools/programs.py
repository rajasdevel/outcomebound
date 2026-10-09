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
stopped by `killpg` on POSIX. On Windows the command also goes into a job object of its own, and
`TerminateJobObject` ends everything in the job at once; `taskkill /T /F` and then `Popen.kill`
are the fallback where there is no job. `start_tree` is how a command starts: on Windows it
starts the command suspended, joins it to its job, and only then lets it run, so that nothing the
command starts can be outside the job.

What it does not decide: whether a program is the right one, or what a caller does where none is
found. `require` raises `FileNotFoundError`, which every caller of a process already reads.

`windows=`, `environment=` and `jobs=` exist so that a test can run the Windows branch beside a
scratch folder, and with its own job calls, on any platform.
"""

from __future__ import annotations

import contextlib
import errno
import functools
import os
import shutil
import signal
import subprocess
import weakref
from collections.abc import Mapping, Sequence
from pathlib import Path, PureWindowsPath
from typing import Any, Protocol

__all__ = [
    "command",
    "environment_value",
    "find",
    "new_group",
    "posix_shell",
    "require",
    "resolve",
    "shell_environment",
    "start_tree",
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
# What the Windows job calls are told: `JobObjectExtendedLimitInformation` carries the limit flags,
# and `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` ends every process in the job when its last handle
# closes. No breakaway flag is set, so no descendant can leave the job.
JOB_EXTENDED_LIMIT_INFORMATION = 9
JOB_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
# The exit code of a process that `TerminateJobObject` ends, as `Popen.kill` gives on Windows.
JOB_EXIT_CODE = 1
# The creation flag that starts a process with its first thread suspended (`CREATE_SUSPENDED`;
# `subprocess` has no name for it), and what resuming that thread takes: a snapshot of the
# system's threads (`TH32CS_SNAPTHREAD`), the right to suspend and resume one
# (`THREAD_SUSPEND_RESUME`), and `ResumeThread`'s failure value, `(DWORD) -1`.
CREATE_SUSPENDED = 0x4
TH32CS_SNAPTHREAD = 0x4
THREAD_SUSPEND_RESUME = 0x2
RESUME_FAILED = 0xFFFFFFFF


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


class Jobs(Protocol):
    """The five calls that make a Windows job object work. `programs` uses the system's
    (`_Kernel32`); a test passes its own."""

    def create(self) -> int | None:
        """A new job that ends every process in it when its last handle closes, or None."""
        ...

    def assign(self, job: int, process: subprocess.Popen[bytes]) -> bool:
        """Put a process in the job. False where the process cannot join it."""
        ...

    def resume(self, process: subprocess.Popen[bytes]) -> bool:
        """Let a process that started suspended (`CREATE_SUSPENDED`) run. False where it could
        not be resumed."""
        ...

    def terminate(self, job: int) -> bool:
        """End every process in the job. False where that did not work."""
        ...

    def close(self, job: int) -> None:
        """Let go of the job's handle."""
        ...


def _limit_information() -> Any:
    """`JOBOBJECT_EXTENDED_LIMIT_INFORMATION` as `ctypes` lays it out, with the one limit a job
    here has set: `JOB_LIMIT_KILL_ON_JOB_CLOSE`. The layout is 144 bytes where a pointer is 8
    bytes and 112 where it is 4, with `LimitFlags` at offset 16. A wrong layout would make
    `SetInformationJobObject` fail or set another limit; it is built from sizes alone, so a test
    checks it on any platform."""

    import ctypes

    class Basic(ctypes.Structure):
        _fields_ = (
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        )

    class Counters(ctypes.Structure):
        _fields_ = (
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        )

    class Extended(ctypes.Structure):
        _fields_ = (
            ("BasicLimitInformation", Basic),
            ("IoInfo", Counters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        )

    limits = Extended()
    limits.BasicLimitInformation.LimitFlags = JOB_LIMIT_KILL_ON_JOB_CLOSE
    return limits


def _thread_entry() -> Any:
    """The `THREADENTRY32` class as `ctypes` lays it out: seven four-byte members, 28 bytes, the
    thread id at offset 8 and the id of the process that owns it at 12. A test checks it on any
    platform."""

    import ctypes

    class ThreadEntry(ctypes.Structure):
        _fields_ = (
            ("dwSize", ctypes.c_uint32),
            ("cntUsage", ctypes.c_uint32),
            ("th32ThreadID", ctypes.c_uint32),
            ("th32OwnerProcessID", ctypes.c_uint32),
            ("tpBasePri", ctypes.c_int32),
            ("tpDeltaPri", ctypes.c_int32),
            ("dwFlags", ctypes.c_uint32),
        )

    return ThreadEntry


class _Kernel32:
    """The job calls of the running Windows, on a private copy of `kernel32.dll` so that no other
    code's prototypes change. Raises `OSError` where there is no Windows API to call.

    A process resumes through the documented thread calls: `CreateToolhelp32Snapshot` lists the
    system's threads, and `ResumeThread` runs each one that the process owns. `Popen` closes the
    handle of the process's first thread when it returns, and `NtResumeProcess`, which takes the
    process handle that `Popen` keeps, is a native call of `ntdll.dll` that the Win32 reference
    does not list: a documented call that needs a list is chosen over a call that needs none and
    that Microsoft may change."""

    def __init__(self) -> None:
        import ctypes

        loader = getattr(ctypes, "WinDLL", None)
        if loader is None:
            raise OSError("this platform has no Windows API")
        self._ctypes = ctypes
        kernel = loader("kernel32")
        handle, number = ctypes.c_void_p, ctypes.c_uint32
        self._entry_type = _thread_entry()
        self._invalid = ctypes.c_void_p(-1).value
        self._snapshot = kernel.CreateToolhelp32Snapshot
        self._snapshot.argtypes, self._snapshot.restype = [number, number], handle
        entry = ctypes.POINTER(self._entry_type)
        self._first = kernel.Thread32First
        self._first.argtypes, self._first.restype = [handle, entry], ctypes.c_int
        self._next = kernel.Thread32Next
        self._next.argtypes, self._next.restype = [handle, entry], ctypes.c_int
        self._open_thread = kernel.OpenThread
        self._open_thread.argtypes = [number, ctypes.c_int, number]
        self._open_thread.restype = handle
        self._resume_thread = kernel.ResumeThread
        self._resume_thread.argtypes, self._resume_thread.restype = [handle], number
        self._create = kernel.CreateJobObjectW
        self._create.argtypes, self._create.restype = [handle, ctypes.c_wchar_p], handle
        self._set = kernel.SetInformationJobObject
        self._set.argtypes, self._set.restype = [handle, ctypes.c_int, handle, number], ctypes.c_int
        self._assign = kernel.AssignProcessToJobObject
        self._assign.argtypes, self._assign.restype = [handle, handle], ctypes.c_int
        self._terminate = kernel.TerminateJobObject
        self._terminate.argtypes, self._terminate.restype = [handle, number], ctypes.c_int
        self._close = kernel.CloseHandle
        self._close.argtypes, self._close.restype = [handle], ctypes.c_int
        # Kept for its address to stay valid.
        self._limits = _limit_information()
        self._address, self._size = ctypes.addressof(self._limits), ctypes.sizeof(self._limits)

    def create(self) -> int | None:
        job = self._create(None, None)
        if not job:
            return None
        if self._set(job, JOB_EXTENDED_LIMIT_INFORMATION, self._address, self._size):
            return int(job)
        self._close(job)
        return None

    def assign(self, job: int, process: subprocess.Popen[bytes]) -> bool:
        # `Popen` keeps the handle that `CreateProcess` returned, which has the access to join a
        # job; the process id would have to be opened again, after the id could have been reused.
        handle = getattr(process, "_handle", None)
        return handle is not None and bool(self._assign(job, int(handle)))

    def resume(self, process: subprocess.Popen[bytes]) -> bool:
        """Run each thread the process owns: a process that started suspended has one. The
        process's handle is open, so its id cannot have passed to another process."""

        ctypes = self._ctypes
        snapshot = self._snapshot(TH32CS_SNAPTHREAD, 0)
        if snapshot is None or snapshot == self._invalid:
            return False
        resumed = False
        try:
            entry = self._entry_type()
            entry.dwSize = ctypes.sizeof(entry)
            more = self._first(snapshot, ctypes.byref(entry))
            while more:
                if entry.th32OwnerProcessID == process.pid:
                    if not self._run(entry.th32ThreadID):
                        return False
                    resumed = True
                entry.dwSize = ctypes.sizeof(entry)
                more = self._next(snapshot, ctypes.byref(entry))
        finally:
            self._close(snapshot)
        return resumed

    def _run(self, thread_id: int) -> bool:
        thread = self._open_thread(THREAD_SUSPEND_RESUME, False, thread_id)
        if not thread:
            return False
        try:
            return int(self._resume_thread(thread)) != RESUME_FAILED
        finally:
            self._close(thread)

    def terminate(self, job: int) -> bool:
        return bool(self._terminate(job, JOB_EXIT_CODE))

    def close(self, job: int) -> None:
        self._close(job)


@functools.lru_cache(maxsize=1)
def _system_jobs() -> Jobs | None:
    """The job calls of this machine, or None where it has none (not Windows, or a Windows API
    that cannot be loaded). Made once."""

    if os.name != "nt":
        return None
    try:
        return _Kernel32()
    except (OSError, AttributeError, ImportError):
        return None


class _Job:
    """One command's job. Its handle closes when this object goes, and a job whose last handle
    closes ends every process still in it."""

    def __init__(self, api: Jobs, handle: int) -> None:
        self.handle = handle
        self._api = api
        self._finalizer = weakref.finalize(self, api.close, handle)

    def terminate(self) -> bool:
        return self._api.terminate(self.handle)

    def close(self) -> None:
        self._finalizer()


# The job of each tracked process, held for as long as the process object is.
_JOBS: weakref.WeakKeyDictionary[subprocess.Popen[bytes], _Job] = weakref.WeakKeyDictionary()


def track_tree(
    process: subprocess.Popen[bytes], *, windows: bool | None = None, jobs: Jobs | None = None
) -> bool:
    """On Windows, put a process into a job object of its own, so that `stop_tree` ends it and
    everything it starts in one call, however many processes there are and however loaded the
    machine. This is the join step of `start_tree`, which a caller uses to start a command.

    True where a job holds the process. False where there is none to make or join: not Windows,
    no Windows API, a job that refuses nesting, a process that has already ended. `stop_tree`
    then falls back to `taskkill`. Never raises, and changes nothing off Windows.

    A job holds only the processes started after the process joined it. A process that is running
    when it joins has had that time to start others, which stay outside the job. `start_tree`
    closes that time: it starts the process suspended, so that nothing has run when it joins.
    Called on a process that is already running, this leaves the time open.

    The job ends what is still running in it when the process object is let go. A command that
    ended by itself and left a process behind has that process ended then."""

    if not _windows(windows):
        return False
    with contextlib.suppress(Exception):
        api = _system_jobs() if jobs is None else jobs
        handle = None if api is None else api.create()
        if api is None or handle is None:
            return False
        job = _Job(api, handle)
        if api.assign(handle, process):
            _JOBS[process] = job
            return True
        job.close()
    return False


def _resumed(process: subprocess.Popen[bytes], api: Jobs) -> bool:
    """Whether a process that started suspended now runs. A resume that raises counts as one that
    failed."""

    try:
        return bool(api.resume(process))
    except Exception:
        return False


def _abandon(process: subprocess.Popen[bytes]) -> None:
    """End a process that must not be left suspended, holding the pipes its caller waits on: its
    job where it joined one, else `taskkill`, and the process itself last. Never raises."""

    stop_tree(process, windows=True)
    with contextlib.suppress(OSError):
        process.kill()
    with contextlib.suppress(subprocess.SubprocessError):
        process.wait(TASKKILL_SECONDS)


def start_tree(
    argv: Sequence[str],
    *,
    windows: bool | None = None,
    jobs: Jobs | None = None,
    **options: Any,
) -> subprocess.Popen[bytes]:
    """Start `argv` with `Popen(argv, **options)` as the leader of a process group that
    `stop_tree` can end whole: the keywords of `new_group`, and on Windows a job object.

    On Windows where the job API loads, the command starts suspended, joins its job
    (`track_tree`), and is then resumed, so that every process it starts is in the job from its
    first instruction. The API loads before the command starts, so that a loaded machine does not
    spend that time with the command running. A join that fails does not stop the command: it
    is resumed, runs without a job, and `stop_tree` falls back to `taskkill`. A resume that fails
    ends the command and raises `OSError`, which every caller already reads as a command that
    could not start. Where there is no job API the command starts at once, as off Windows,
    where this is `Popen` with a group of its own.

    `options` are `Popen`'s other keywords, and hold neither `creationflags` nor
    `start_new_session`: the group is this function's. Raises what `Popen` raises, and
    `OSError` for a failed resume. A `BaseException` that arrives
    between the start and the resume, a Ctrl-C or a signal handler's exception, stops the command
    before it propagates."""

    on_windows = _windows(windows)
    api: Jobs | None = None
    if on_windows:
        with contextlib.suppress(Exception):
            api = _system_jobs() if jobs is None else jobs
    group = new_group(windows=on_windows)
    if api is not None:
        group["creationflags"] |= CREATE_SUSPENDED
    process: subprocess.Popen[bytes] = subprocess.Popen(argv, **group, **options)
    if api is None:
        return process
    try:
        track_tree(process, windows=True, jobs=api)
        resumed = _resumed(process, api)
    except BaseException:
        _abandon(process)
        raise
    if not resumed:
        _abandon(process)
        raise OSError("the command started but could not be resumed, and was stopped")
    return process


def _end_job(process: subprocess.Popen[bytes]) -> bool:
    """Whether the job the process runs in ended everything in it. False for a process that no
    job holds, and where the job could not end it."""

    with contextlib.suppress(Exception):
        job = _JOBS.get(process)
        return job is not None and job.terminate()
    return False


def stop_tree(process: subprocess.Popen[bytes], *, windows: bool | None = None) -> None:
    """Kill the process and everything it started, and never raise. A process that did not start
    with `new_group` has no group of its own on POSIX; then only it is killed. On Windows the
    job `track_tree` made ends the whole tree at once; where no job holds the process, or it
    could not end it, `taskkill /T /F` ends the tree, and the process is killed after it where
    taskkill could not run."""

    if _windows(windows):
        if _end_job(process):
            return
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
