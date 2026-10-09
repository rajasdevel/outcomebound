"""`programs`: finding a program on PATH and stopping the tree it started.

The Windows branch runs here beside scratch folders (`windows=True`, a `PATHEXT` and a folder
laid out as Git for Windows lays it out), and with job calls a test supplies (`FakeJobs`); what
only a Windows process shows, that a job object ends a real tree, that `taskkill` does where
there is no job, and that `sh.exe` runs a line, is settled by the Windows CI job, which runs the
tests below that need Windows, `tests/test_finish_check.py` and the floor's tests against the
real thing.
"""

from __future__ import annotations

import contextlib
import ctypes
import gc
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import explorable_browser, finish_check, programs, validation
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


# --- a Windows job object holds a command's tree ----------------------------------

JOB = 7001
SLEEP = [sys.executable, "-c", "import time; time.sleep(60)"]


class FakeJobs:
    """The four job calls a Windows machine has, as a test has them: each call is recorded; one
    named in `fail` reports failure, one in `raises` raises, as the real call could."""

    def __init__(self, fail: Collection[str] = (), raises: Collection[str] = ()) -> None:
        self.calls: list[tuple[str, int | None]] = []
        self.joined: list[int] = []
        self.fail, self.raises = set(fail), set(raises)

    def _call(self, name: str, job: int | None = None) -> bool:
        self.calls.append((name, job))
        if name in self.raises:
            raise OSError(name)
        return name not in self.fail

    def create(self) -> int | None:
        return JOB if self._call("create") else None

    def assign(self, job: int, process: subprocess.Popen[bytes]) -> bool:
        self.joined.append(process.pid)
        return self._call("assign", job)

    def terminate(self, job: int) -> bool:
        return self._call("terminate", job)

    def close(self, job: int) -> None:
        self.calls.append(("close", job))


@pytest.fixture
def sleeper() -> Any:
    process = subprocess.Popen(SLEEP)
    yield process
    process.kill()
    process.wait()


def taskkill_asked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[list[str]]:
    """Replace the `taskkill` run by one that cannot start, and return the argvs it was asked."""

    asked: list[list[str]] = []

    def cannot(argv: list[str], **options: Any) -> None:
        asked.append(argv)
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(programs.subprocess, "run", cannot)
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path / "Windows"))
    return asked


def test_the_job_limit_structure_has_the_layout_windows_reads() -> None:
    """Breaks if the structure `SetInformationJobObject` is given has another size than the
    Windows SDK's (144 bytes where a pointer is 8 bytes, 112 where it is 4), or holds anything
    but the kill-on-close flag (0x2000, at offset 16, in a little-endian DWORD): the call would
    fail, or set another limit, on a machine this suite cannot run on, and `stop_tree` would
    fall back to `taskkill` with nothing to show it."""

    limits = programs._limit_information()
    assert ctypes.sizeof(limits) == (144 if ctypes.sizeof(ctypes.c_void_p) == 8 else 112)
    expected = bytearray(ctypes.sizeof(limits))
    expected[16:20] = (0x2000).to_bytes(4, "little")
    assert bytes(limits) == bytes(expected)


def test_windows_puts_a_command_in_a_job_of_its_own_when_it_starts(sleeper: Any) -> None:
    """Breaks if the command is never given to a job, or is given to one before the job can end
    what is in it, so that `stop_tree` has no job to end: a grandchild of a loaded machine then
    outlives `taskkill`."""

    jobs = FakeJobs()
    assert programs.track_tree(sleeper, windows=True, jobs=jobs) is True
    assert jobs.calls == [("create", None), ("assign", JOB)]
    assert jobs.joined == [sleeper.pid]


def test_windows_ends_a_tracked_tree_through_its_job_and_asks_taskkill_nothing(
    sleeper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Breaks if a tree that a job holds is still stopped by `taskkill`, whose walk over parent
    ids misses a process under load, or if the job is never ended."""

    asked = taskkill_asked(monkeypatch, tmp_path)
    jobs = FakeJobs()
    programs.track_tree(sleeper, windows=True, jobs=jobs)

    programs.stop_tree(sleeper, windows=True)

    assert jobs.calls[-1] == ("terminate", JOB)
    assert asked == []


@pytest.mark.parametrize("failure", ["returns", "raises"])
def test_windows_falls_back_to_taskkill_then_kill_where_the_job_cannot_end_the_tree(
    sleeper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    """Breaks if a job that cannot be ended (it reports failure, or the call raises) leaves the
    tree running, if `taskkill` is not asked first, if the process is not killed after a
    `taskkill` that cannot run (here it cannot), or if the failure escapes `stop_tree`."""

    asked = taskkill_asked(monkeypatch, tmp_path)
    jobs = FakeJobs(**{"fail" if failure == "returns" else "raises": ["terminate"]})
    assert programs.track_tree(sleeper, windows=True, jobs=jobs) is True

    programs.stop_tree(sleeper, windows=True)

    assert jobs.calls[-1] == ("terminate", JOB)
    assert [argv[1:] for argv in asked] == [["/T", "/F", "/PID", str(sleeper.pid)]]
    assert sleeper.wait(timeout=30) != 0


@pytest.mark.parametrize(
    ("call", "failure", "made"),
    [
        ("create", "fail", False),
        ("create", "raises", False),
        ("assign", "fail", True),
        ("assign", "raises", True),
    ],
)
def test_windows_makes_no_job_where_one_cannot_be_made_or_joined_and_stops_by_taskkill(
    sleeper: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    call: str,
    failure: str,
    made: bool,
) -> None:
    """Breaks if a job that cannot be made, or that the process cannot join (an older Windows,
    a job that forbids nesting), raises out of `track_tree`, leaves `stop_tree` to end an empty
    job and skip `taskkill`, or leaves a job handle open; and if the process is not killed."""

    asked = taskkill_asked(monkeypatch, tmp_path)
    jobs = FakeJobs(**{failure: [call]})

    assert programs.track_tree(sleeper, windows=True, jobs=jobs) is False
    gc.collect()
    assert (("close", JOB) in jobs.calls) is made

    programs.stop_tree(sleeper, windows=True)

    assert ("terminate", JOB) not in jobs.calls
    assert [argv[1:] for argv in asked] == [["/T", "/F", "/PID", str(sleeper.pid)]]
    assert sleeper.wait(timeout=30) != 0


def test_a_job_is_held_while_its_command_is_and_let_go_with_it() -> None:
    """Breaks if the job's handle closes while the command is still held, which ends the whole
    command at once (a job ends what is in it when its last handle closes), or if the handle is
    never closed."""

    jobs = FakeJobs()
    process = subprocess.Popen(SLEEP)
    try:
        programs.track_tree(process, windows=True, jobs=jobs)
        gc.collect()
        assert ("close", JOB) not in jobs.calls
    finally:
        process.kill()
        process.wait()
    del process
    gc.collect()
    assert jobs.calls[-1] == ("close", JOB)


def test_off_windows_a_command_gets_no_job(sleeper: Any) -> None:
    """Breaks if a POSIX run calls the job functions, which do not exist there, or loads the
    Windows API."""

    jobs = FakeJobs()
    assert programs.track_tree(sleeper, windows=False, jobs=jobs) is False
    assert jobs.calls == []
    if not WINDOWS:
        assert programs.track_tree(sleeper) is False


def test_a_windows_stop_on_a_machine_with_no_windows_api_still_stops_by_taskkill(
    sleeper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Breaks if `windows=True` without a job API (this host, or a Windows whose API cannot be
    loaded) raises or skips the fallback."""

    asked = taskkill_asked(monkeypatch, tmp_path)
    monkeypatch.setattr(programs, "_system_jobs", lambda: None)

    assert programs.track_tree(sleeper, windows=True) is False
    programs.stop_tree(sleeper, windows=True)

    assert len(asked) == 1
    assert sleeper.wait(timeout=30) != 0


def run_one_command(tmp_path: Path) -> None:
    finish_check.run_one(tmp_path, "exit 0", 30)


def run_one_claim(tmp_path: Path) -> None:
    validation._execute([sys.executable, "-c", "pass"], tmp_path, 30)


def run_one_page(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text("x", encoding="utf-8")
    explorable_browser.run_page(sys.executable, page, 30)


def run_one_eval_command(tmp_path: Path) -> None:
    from evals.processes import bounded_command

    bounded_command([sys.executable, "-c", "pass"], timeout=30)


@pytest.mark.parametrize(
    "start",
    [run_one_command, run_one_claim, run_one_page, run_one_eval_command],
    ids=["finish-check", "validation", "explorable-browser", "eval-command"],
)
def test_every_caller_that_starts_a_command_puts_it_in_a_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, start: Callable[[Path], None]
) -> None:
    """Breaks if a caller drops its `track_tree` call: nothing else fails then, since a command
    without a job is stopped by `taskkill`, which only a loaded Windows machine shows to miss a
    process."""

    if start is run_one_command and programs.posix_shell() is None:
        pytest.skip("no POSIX shell to run a Done line")
    joined: list[subprocess.Popen[bytes]] = []
    real = programs.track_tree

    def record(process: subprocess.Popen[bytes], **options: Any) -> bool:
        joined.append(process)
        return real(process, **options)

    monkeypatch.setattr(programs, "track_tree", record)

    start(tmp_path)

    assert len(joined) == 1


@pytest.mark.skipif(not WINDOWS, reason="a job object is a Windows object")
def test_a_real_job_ends_a_commands_grandchild_without_taskkill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the command is not put in a job (a `ctypes` call that fails is swallowed and
    `stop_tree` falls back to `taskkill`, which every other test passes), if the job does not
    end a process two levels below the command, or if it needs `taskkill` to."""

    leaf = tmp_path / "leaf.py"
    leaf.write_text("import time; time.sleep(60)\n", encoding="utf-8")
    middle = tmp_path / "middle.py"
    middle.write_text(
        "import subprocess, sys\n"
        "leaf = subprocess.Popen([sys.executable, sys.argv[1]])\n"
        "with open(sys.argv[2], 'w') as handle:\n"
        "    handle.write(str(leaf.pid))\n"
        "leaf.wait()\n",
        encoding="utf-8",
    )
    top = tmp_path / "top.py"
    top.write_text(
        "import subprocess, sys\nsubprocess.Popen([sys.executable, *sys.argv[1:]]).wait()\n",
        encoding="utf-8",
    )
    pid = tmp_path / "leaf.pid"
    process = subprocess.Popen(
        [sys.executable, str(top), str(middle), str(leaf), str(pid)], **programs.new_group()
    )
    try:
        assert programs.track_tree(process) is True, "the command was not put in a job"
        deadline = time.monotonic() + 30
        while not (pid.exists() and pid.read_text(encoding="utf-8").strip()):
            assert time.monotonic() < deadline, "the command never wrote its pid"
            time.sleep(0.05)
        grandchild = int(pid.read_text(encoding="utf-8"))

        def never(*arguments: Any) -> str:
            raise AssertionError("the job did not end the tree and taskkill was asked")

        monkeypatch.setattr(programs, "_taskkill", never)
        programs.stop_tree(process)

        assert process.wait(timeout=30) != 0
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and running(grandchild):
            time.sleep(0.1)
        assert not running(grandchild), "the grandchild outlived its job"
    finally:
        process.kill()
        process.wait()
