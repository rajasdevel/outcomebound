"""The engine's launchers: `scripts/outcomebound` for a checkout, and the package's console entry
point (`outcomebound_tools/launcher.py`) for an install.

The engine, started the way the launchers start it (isolated, UTF-8), runs each verb's module,
exits 1 and never 2 for a word it cannot run, writes UTF-8 with LF line ends whatever the
console's code page, and cannot be shadowed by an `outcomebound_tools` package in the caller's
directory or on the caller's PYTHONPATH. Those tests start the engine through the running Python,
so they run on every platform. The checkout's launcher is a POSIX sh script: it resolves its own
checkout through a symlink and exits 127, not 2, when it cannot start; those tests run where `sh`
does. The entry point re-runs this Python as the engine's command, on POSIX in place of itself and
on Windows as a child; the installed command is tested in `test_package.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from outcomebound_tools import launcher

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "scripts" / "outcomebound"
POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="the checkout's launcher is a POSIX sh script"
)
# What the checkout's launcher runs after `python -I -X utf8 -c`: the checkout first on the path.
CHECKOUT_ENGINE = """import runpy, sys
sys.path.insert(0, sys.argv[1])
sys.argv = ["outcomebound", *sys.argv[2:]]
runpy.run_module("outcomebound_tools", run_name="__main__", alter_sys=True)
"""
VERBS = (
    "adopt",
    "tickets",
    "brief",
    "floor",
    "validation",
    "fragments",
    "discovery",
    "instructions",
    "finish-check",
)


def engine(
    *arguments: str, cwd: Path, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """This checkout's engine, run as `scripts/outcomebound` runs it, through the running Python."""

    return subprocess.run(
        [sys.executable, "-I", "-X", "utf8", "-c", CHECKOUT_ENGINE, str(ROOT), *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def launch(
    *arguments: str, cwd: Path, launcher: Path = LAUNCHER, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """The same through the checkout's sh launcher, or a link to it."""

    return subprocess.run(
        [str(launcher), *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@POSIX_ONLY
def test_the_launcher_is_an_executable_posix_script() -> None:
    assert os.access(LAUNCHER, os.X_OK)
    assert LAUNCHER.read_text(encoding="utf-8").startswith("#!/bin/sh\n")


@POSIX_ONLY
def test_a_symlink_on_another_directory_runs_this_checkout(tmp_path: Path) -> None:
    bin_dir, elsewhere = tmp_path / "bin", tmp_path / "elsewhere"
    bin_dir.mkdir()
    elsewhere.mkdir()
    link = bin_dir / "outcomebound"
    link.symlink_to(LAUNCHER)
    subprocess.run(["git", "init", "-q", str(elsewhere)], check=True)

    home = launch("home", cwd=elsewhere, launcher=link)
    detected = launch("adopt", str(elsewhere), "--detect", cwd=elsewhere, launcher=link)

    assert home.returncode == 0 and Path(home.stdout.strip()) == ROOT
    assert detected.returncode == 0, detected.stderr
    assert detected.stdout.split()[:2] == ["outcomebound", "adopt"]
    assert [path.name for path in elsewhere.iterdir()] == [".git"]


@POSIX_ONLY
def test_the_launcher_runs_a_python_on_an_absolute_path_entry_and_never_a_relative_one(
    tmp_path: Path,
) -> None:
    """A `python` that is not Python 3.10 or later, or sits in the caller's directory, is
    passed over; with none left the launcher exits 127, never 2."""

    bin_dir, here = tmp_path / "bin", tmp_path / "here"
    bin_dir.mkdir()
    here.mkdir()
    tools = {name: shutil.which(name) for name in ("dirname", "readlink")}
    for name, path in tools.items():
        (bin_dir / name).symlink_to(str(path))
    stub = "#!/bin/sh\nexit 9\n"
    for folder in (bin_dir, here):
        (folder / "python3").write_text(stub, encoding="utf-8")
        (folder / "python3").chmod(0o755)
    old = {"PATH": f"{here}{os.pathsep}{bin_dir}"}  # `here` is absolute, but its python3 is a stub

    refused = launch("home", cwd=tmp_path, environment=old)
    (bin_dir / "python").symlink_to(sys.executable)
    relative = launch("home", cwd=here, environment={"PATH": f".{os.pathsep}{bin_dir}"})

    assert refused.returncode == 127, refused.stderr
    assert "no Python 3.10 or later" in refused.stderr
    assert relative.returncode == 0, relative.stderr
    assert Path(relative.stdout.strip()) == ROOT


@POSIX_ONLY
def test_the_launcher_beside_no_engine_exits_127(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    copy = tmp_path / "scripts" / "outcomebound"
    copy.write_bytes(LAUNCHER.read_bytes())
    copy.chmod(0o755)

    done = launch("home", cwd=tmp_path, launcher=copy)

    assert done.returncode == 127 and "no engine beside" in done.stderr


def test_an_engine_in_the_callers_directory_or_path_is_never_run(tmp_path: Path) -> None:
    decoy = tmp_path / "outcomebound_tools"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    for name in ("__main__", "home", "adopt", "fileplan", "fragments", "identity"):
        (decoy / f"{name}.py").write_text("raise SystemExit(99)\n", encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": str(tmp_path)}
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    result = engine("adopt", str(tmp_path), "--detect", cwd=tmp_path, environment=environment)

    assert result.returncode == 0, result.stderr
    assert result.stdout.split()[:2] == ["outcomebound", "adopt"]


# Each verb's own verbs, whose `--help` a reader reaches as `outcomebound <verb> <sub> --help`.
SUBVERBS = {
    "tickets": ("check", "brief"),
    "floor": ("propose", "apply", "check", "baseline", "ratchet", "provision", "remove"),
    "fragments": ("compose", "detect"),
}
HELPS = [(verb,) for verb in VERBS] + [
    (verb, sub) for verb, subs in SUBVERBS.items() for sub in subs
]


@pytest.mark.parametrize("words", HELPS, ids=" ".join)
def test_every_verb_runs_its_module_by_path_and_its_help_names_the_launcher(
    tmp_path: Path, words: tuple[str, ...]
) -> None:
    """A usage line an agent copies runs from any directory: it names `outcomebound <verb>`,
    never `python3 -m outcomebound_tools.<module>`, which fails outside this checkout."""

    result = engine(*words, "--help", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"usage: outcomebound {' '.join(words)}"), result.stdout
    assert "outcomebound_tools" not in result.stdout


@pytest.mark.parametrize("arguments", [(), ("frobnicate",), ("-m",)])
def test_an_unknown_verb_lists_the_verbs_and_exits_1_never_2(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    """A harness's stop hook reads exit 2 as holding the turn, so a word the verb table cannot
    run, as an old hook entry may pass, must not hold it."""

    result = engine(*arguments, cwd=tmp_path)

    assert result.returncode == 1
    assert all(verb in result.stderr.split() for verb in ("home", *VERBS))


def test_a_command_the_engine_runs_inherits_the_callers_environment(tmp_path: Path) -> None:
    """The engine runs isolated without exporting anything, so a project's own check keeps
    its working directory on `sys.path` and sees the caller's PYTHONPATH."""

    probe = (
        "import os, sys; "
        "sys.exit(0 if not os.environ.get('PYTHONSAFEPATH') "
        "and os.environ.get('PYTHONPATH') == 'callers' and sys.path[0] == '' else 1)"
    )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "version": 1,
                "cwd": ".",
                "timeout_seconds": 60,
                "claims": [
                    {
                        "name": "environment",
                        "risk": "the launcher leaks its interpreter settings into a check",
                        "kind": "test",
                        "required": True,
                        "command": [sys.executable, "-c", probe],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONSAFEPATH"} | {
        "PYTHONPATH": "callers"
    }

    result = engine("validation", str(plan), cwd=tmp_path, environment=environment)

    assert result.returncode == 0, result.stdout + result.stderr


RUNNER = ROOT / ".agents" / "tools" / "runner"


@POSIX_ONLY
def test_the_runner_puts_this_checkouts_engine_first_from_anywhere(tmp_path: Path) -> None:
    """In a worktree, `outcomebound` on PATH may run another checkout: the runner makes every
    command it starts name this one, through OUTCOMEBOUND_HOME and the launcher first on PATH."""

    other = tmp_path / "other-bin"
    other.mkdir()
    (other / "outcomebound").write_text("#!/bin/sh\necho elsewhere\n", encoding="utf-8")
    (other / "outcomebound").chmod(0o755)
    environment = {**os.environ, "PATH": f"{other}{os.pathsep}{os.environ['PATH']}"}

    done = subprocess.run(
        [str(RUNNER), "sh", "-c", 'echo "$OUTCOMEBOUND_HOME"; outcomebound home'],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    bare = subprocess.run([str(RUNNER)], capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    assert [Path(line) for line in done.stdout.split()] == [ROOT, ROOT]
    assert bare.returncode == 2 and "usage:" in bare.stderr


# A Windows process's stdout into a pipe: the ANSI code page, and CRLF line ends.
WINDOWS_PIPE = """import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="cp1252", newline="\\r\\n")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="cp1252", newline="\\r\\n")
sys.path.insert(0, sys.argv[1])
from outcomebound_tools.__main__ import main
sys.exit(main(sys.argv[2:]))
"""


@pytest.mark.parametrize(
    "arguments",
    [("home",), ("fragments", "compose", "--inline", "--fragments", "python")],
    ids=["a path", "text with characters cp1252 lacks"],
)
def test_a_verb_writes_utf8_with_lf_line_ends_into_a_cp1252_crlf_pipe(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    """The engine's text is the same bytes on every platform: a script `tickets publish` prints
    runs under `sh`, and `$(outcomebound home)` carries no stray carriage return."""

    if arguments[0] == "fragments":
        arguments = (*arguments, "--source", str(ROOT), "--target", str(tmp_path))

    done = subprocess.run(
        [sys.executable, "-I", "-c", WINDOWS_PIPE, str(ROOT), *arguments],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert b"\r" not in done.stdout and done.stdout.endswith(b"\n")
    text = done.stdout.decode("utf-8")
    assert arguments[0] == "home" or "≠" in text


def test_the_entry_point_runs_the_environments_python_isolated_in_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine's command line: this Python, `-I`, `-X utf8`, the caller's arguments, and no
    change to the caller's environment."""

    started: list[list[str]] = []

    def run(argv: list[str]) -> int:
        started.append(argv)
        return 5

    monkeypatch.setattr(launcher, "_run", run)
    environment = dict(os.environ)

    assert launcher.main(["adopt", ".", "--check"]) == 5

    command = [sys.executable, "-I", "-X", "utf8", "-m", "outcomebound_tools"]
    assert started == [[*command, "adopt", ".", "--check"]]
    assert dict(os.environ) == environment


def test_the_entry_point_waits_for_a_child_and_returns_its_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same on every platform: Windows has no call that replaces the process, and the
    process a harness waits for must end when the check does."""

    def child(arguments: list[str]) -> list[str]:
        return [sys.executable, "-c", f"raise SystemExit({arguments[0]})"]

    monkeypatch.setattr(launcher, "command", child)

    assert [launcher.main([code]) for code in ("0", "1", "7")] == [0, 1, 7]


def test_a_ctrl_c_while_the_child_runs_is_left_to_the_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The console sends Ctrl-C to the child as well. This process must stay to return the
    child's exit code, and must have its own handler back once the child has ended."""

    code = "import time; time.sleep(0.3); raise SystemExit(130)"
    monkeypatch.setattr(launcher, "command", lambda arguments: [sys.executable, "-c", code])
    before = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
    timer = threading.Timer(0.1, signal.raise_signal, [signal.SIGINT])

    timer.start()
    result = launcher.main([])
    timer.join()

    assert result == 130
    assert (signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)) == before


@pytest.mark.skipif(os.name == "nt", reason="`os.kill` with SIGTERM ends a process on Windows")
def test_a_sigterm_to_the_entry_point_reaches_the_child_and_reads_as_a_shell_reports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A harness that stops a hook with SIGTERM stops the engine, not only this process."""

    code = "import time; time.sleep(30)"
    monkeypatch.setattr(launcher, "command", lambda arguments: [sys.executable, "-c", code])
    timer = threading.Timer(0.3, os.kill, [os.getpid(), signal.SIGTERM])

    timer.start()
    result = launcher.main([])
    timer.join()

    assert result == 128 + signal.SIGTERM


def test_an_engine_that_cannot_start_exits_127_never_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A stop hook reads exit 2 as holding the turn, and a missing Python is no reason to."""

    monkeypatch.setattr(sys, "executable", str(tmp_path / "no-python"))

    assert launcher.main(["home"]) == 127
    assert "cannot start the engine" in capsys.readouterr().err

    monkeypatch.setattr(sys, "executable", "")

    assert launcher.main(["home"]) == 127
    assert "does not name its own file" in capsys.readouterr().err
