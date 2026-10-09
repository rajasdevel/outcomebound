"""`outcomebound finish-check`, the verb a harness's stop hook runs.

Each test runs the launcher in a real subprocess on a scratch Git repository under `tmp_path`,
with the hook's input on stdin in the row's own shape, and reads the JSON the harness would read.
Each names the break it catches.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import finish_check, programs
from tests.portable import WINDOWS, engine, posix_only, write
from tests.processes import running

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git") or "git"


def q(path: str | Path) -> str:
    """A file as a Done line, which a POSIX shell runs on every platform, writes it: forward
    slashes, which Git's shell on Windows reads where it would eat a backslash, and quoted."""

    return shlex.quote(Path(path).as_posix())


def system_path() -> list[str]:
    """The PATH entries a test that replaces PATH keeps so the verb can start Git and its shell:
    the system's on POSIX, and on Windows the folders of the `git.exe` and `sh.exe` it found."""

    if not WINDOWS:
        return ["/usr/bin", "/bin"]
    found = [programs.find("git"), programs.posix_shell()]
    return [str(Path(path).parent) for path in found if path is not None]


# The stop input each row sends, the guard unset, `cwd` added per run; the other fields are the
# rows' own.
INPUT: dict[str, dict[str, Any]] = {
    "claude-code": {
        "session_id": "s",
        "transcript_path": "/dev/null",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "background_tasks": [],
    },
    "codex": {
        "session_id": "s",
        "turn_id": "t",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": "done",
        "permission_mode": "default",
    },
}
ROWS = sorted(INPUT)


def target(path: Path, done: list[str]) -> tuple[Path, str]:
    """A committed Git repository at `path` whose manifest records `done`, and its digest."""

    manifest = {
        "format_version": 2,
        "engine_version": "0",
        "artifacts": [{"kind": "block", "path": "AGENTS.md", "id": "project-facts", "done": done}],
    }
    (path / ".outcomebound").mkdir(parents=True)
    write(path / ".outcomebound/manifest.json", json.dumps(manifest))
    write(path / "src.txt", "one\n")
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    subprocess.run([GIT, "-C", str(path), "add", "."], check=True)
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([GIT, "-C", str(path), *identity, "commit", "-qm", "init"], check=True)
    return path, finish_check.done_digest(done)


def write_transcript(path: Path, row: str, work: str) -> None:
    """A session transcript in `row`'s own shape, as far as the verb reads it: a prompt an hour
    ago, then the model's first work `work` ("future": an hour on, after any mark a test writes;
    "past": two hours ago, before it)."""

    now = datetime.now(timezone.utc)
    hours = (-1, 1) if work == "future" else (-3, -2)
    first, after = ((now + timedelta(hours=h)).isoformat() for h in hours)
    if row == "claude-code":
        lines = [
            {"type": "attachment", "timestamp": first},
            {"type": "user", "timestamp": first, "message": {"role": "user", "content": "hi"}},
            {"type": "assistant", "timestamp": after, "message": {"role": "assistant"}},
        ]
    else:
        lines = [
            {"type": "event_msg", "timestamp": first, "payload": {"type": "task_started"}},
            {
                "type": "response_item",
                "timestamp": first,
                "payload": {"type": "message", "role": "user"},
            },
            {"type": "response_item", "timestamp": after, "payload": {"type": "function_call"}},
        ]
    write(path, "".join(json.dumps(line) + "\n" for line in lines))


def hook(
    row: str,
    digest: str,
    root: Path,
    stdin: bytes | dict[str, Any] | None = None,
    cwd: Path | None = None,
    timeout: int | None = None,
    transcript: str = "future",
) -> tuple[int, dict[str, Any]]:
    """Run the entry as `row` fires it, the input's `cwd` naming where the agent works unless
    `stdin` is given. claude-code runs from the checkout its session started in, which its root
    variable still names, while the agent works in `root`, as after it moves into a worktree;
    codex runs from a directory below `root`, the session's `cwd`."""

    environment = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    if row == "claude-code":
        started = root.parent / "started-here"
        if not started.exists():
            target(started, ["false"])
        environment["CLAUDE_PROJECT_DIR"] = str(started)
        cwd = cwd or started
        working = root
    else:
        cwd = cwd or root / "deeper"
        cwd.mkdir(exist_ok=True)
        working = cwd
    if stdin is None:
        stdin = {**INPUT[row], "cwd": str(working)}
        path = root.parent / f"transcript-{row}.jsonl"
        if transcript in ("future", "past"):
            write_transcript(path, row, transcript)
        elif transcript == "garbage":
            write(path, "not json\n")
        stdin["transcript_path"] = str(path) if transcript != "none" else None
    data = stdin if isinstance(stdin, bytes) else json.dumps(stdin).encode()
    words = engine("finish-check", "--harness", row, "--done", digest)
    if timeout is not None:
        words += ["--timeout", str(timeout)]
    done = subprocess.run(
        words,
        input=data,
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr.decode()
    result: dict[str, Any] = json.loads(done.stdout)
    return done.returncode, result


def mark(
    row: str,
    digest: str,
    root: Path,
    stdin: bytes | dict[str, Any] | None = None,
    cwd: Path | None = None,
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run the turn-start entry as `row` fires it on a prompt: the input's `cwd` names `root`."""

    if stdin is None:
        stdin = {"session_id": "s", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}
    data = stdin if isinstance(stdin, bytes) else json.dumps(stdin).encode()
    words = engine("finish-check", "--mark", "--harness", row, "--done", digest, *(extra or []))
    return subprocess.run(
        words, input=data, cwd=cwd or root, capture_output=True, check=False, timeout=120
    )


@pytest.mark.parametrize("row", ROWS)
def test_a_pass_tells_the_person_and_holds_nothing(tmp_path: Path, row: str) -> None:
    """Breaks if a pass holds the finish or speaks to the model, or if claude-code checks the
    checkout its root variable names, where the session started, instead of the input's `cwd`,
    where the agent works: that checkout's Done list is not the entry's, so nothing would pass."""

    root, digest = target(tmp_path / "t", ["true", "echo ok"])

    _, verdict = hook(row, digest, root)

    assert list(verdict) == ["systemMessage"]
    assert verdict["systemMessage"].startswith("finish-check PASS: true, echo ok, ")
    assert verdict["systemMessage"].endswith("; not reviewed, not landed")


@pytest.mark.parametrize("row", ROWS)
def test_a_failure_holds_the_finish_with_each_command_and_its_output_fenced(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a failure lets the turn end, if a command after the failure runs, or if the
    output reaches the model unfenced or with terminal escapes in it."""

    failing = "printf 'first\\n\\033[31mboom\\033[0m\\n'; exit 3"
    root, digest = target(tmp_path / "t", ["true", failing, "touch ran-third"])

    _, verdict = hook(row, digest, root)

    assert verdict["decision"] == "block" and "systemMessage" not in verdict
    reason = verdict["reason"]
    lines = reason.splitlines()
    assert lines[0].startswith("finish-check FAIL: ")
    assert lines[1].startswith("PASS true (")
    assert lines[2].startswith(f"FAIL {failing}: exit 3 after ")
    assert lines[-4:] == ["```output", "first", "boom", "```"]
    assert "\x1b" not in reason and len(reason) < finish_check.REPORT_CHARACTERS
    assert not (root / "ran-third").exists()


def test_long_output_keeps_its_last_lines_under_the_limit_in_a_longer_fence(
    tmp_path: Path,
) -> None:
    """Breaks if the report outgrows 4,000 characters or keeps the first lines instead of the
    last, or if a fence in the output closes the report's own."""

    printer = "i=0; while [ $i -lt 3000 ]; do echo line $i; i=$((i+1)); done; echo '```'; exit 1"
    root, digest = target(tmp_path / "t", [printer])

    _, verdict = hook("codex", digest, root)

    reason = verdict["reason"]
    assert len(reason) < finish_check.REPORT_CHARACTERS
    assert reason.endswith("line 2999\n```\n````")
    assert "````output\n" in reason and "\nline 0\n" not in reason


def test_commands_that_passed_before_the_failure_never_crowd_it_out(tmp_path: Path) -> None:
    """Breaks if a long Done list pushes the failing command or its output past the limit."""

    passing = ["true " + "#" * 190] * 25
    root, digest = target(tmp_path / "t", [*passing, "echo boom; exit 1"])

    _, verdict = hook("codex", digest, root)

    reason = verdict["reason"]
    assert len(reason) < finish_check.REPORT_CHARACTERS
    assert "PASS the 25 commands before it\nFAIL echo boom; exit 1: exit 1 after " in reason
    assert reason.endswith("```output\nboom\n```")


@pytest.mark.parametrize("row", ROWS)
def test_a_done_list_other_than_the_entrys_runs_nothing_and_holds_nothing(
    tmp_path: Path, row: str
) -> None:
    """Breaks if the entry runs commands the manifest gained after the hook was reviewed."""

    root, _ = target(tmp_path / "t", ["touch ran"])
    written_for = finish_check.done_digest(["make test"])

    _, verdict = hook(row, written_for, root)

    assert list(verdict) == ["systemMessage"]
    assert verdict["systemMessage"].startswith("finish-check UNVERIFIED: ")
    assert "outcomebound adopt" in verdict["systemMessage"]
    assert not (root / "ran").exists()


@pytest.mark.parametrize(
    "stdin",
    [
        {"stop_hook_active": True},
        {"hook_event_name": "Stop"},
        b"not json",
    ],
    ids=["guard-set", "no-guard-field", "unreadable"],
)
def test_a_set_guard_or_unreadable_input_tells_the_person_and_holds_nothing(
    tmp_path: Path, stdin: bytes | dict[str, Any]
) -> None:
    """Breaks if a failure holds the finish a second time, which loops, or holds on input the
    verb could not read; with no `cwd` in the input, the target is found from the process's."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])

    _, verdict = hook("codex", digest, root, stdin=stdin)

    assert list(verdict) == ["systemMessage"]
    assert verdict["systemMessage"].startswith("finish-check FAIL: ")
    assert "```output\nboom\n```" in verdict["systemMessage"]


@pytest.mark.parametrize(
    "waiting",
    [{"background_tasks": [{"task_id": "b1"}]}, {"session_crons": [{"id": "c1"}]}],
    ids=["background-tasks", "session-crons"],
)
def test_claude_code_runs_nothing_while_background_work_or_a_wake_up_waits(
    tmp_path: Path, waiting: dict[str, Any]
) -> None:
    """Breaks if the Done commands run when the session is paused, not finished: background
    work in flight, or a scheduled wake-up that brings the session back."""

    root, digest = target(tmp_path / "t", ["touch ran"])
    paused = {**INPUT["claude-code"], "cwd": str(root), **waiting}

    _, verdict = hook("claude-code", digest, root, stdin=paused)

    assert verdict == {}
    assert not (root / "ran").exists()


def test_an_unchanged_tree_reruns_nothing_and_a_changed_one_runs_again(tmp_path: Path) -> None:
    """Breaks if every turn end reruns the Done commands, or if a tracked edit or an untracked
    file is missed; the digest stays in the Git directory, out of the working tree."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])

    def runs() -> int:
        return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 1
    assert hook("codex", digest, root)[1] == {} and runs() == 1
    write(root / "src.txt", "two\n")
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 2
    write(root / "new.txt", "new\n")
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 3
    assert hook("codex", digest, root)[1] == {} and runs() == 3

    assert (root / ".git" / finish_check.STATE).is_file()
    status = subprocess.run(
        [GIT, "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    assert finish_check.STATE not in status.stdout


def test_an_unchanged_failing_tree_repeats_its_verdict_unheld_and_runs_nothing(
    tmp_path: Path,
) -> None:
    """Breaks if a failure is run again on the tree it just failed on, at the stop after the
    hold or at a later turn end, or if that repeat holds the finish again; a changed tree runs
    again and may hold."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])

    def runs() -> int:
        return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0

    assert hook("codex", digest, root)[1]["decision"] == "block" and runs() == 1
    after_hold = {**INPUT["codex"], "cwd": str(root / "deeper"), "stop_hook_active": True}
    for stdin in (after_hold, None):
        verdict = hook("codex", digest, root, stdin=stdin)[1]
        assert list(verdict) == ["systemMessage"] and runs() == 1
        message = verdict["systemMessage"]
        assert message.startswith("finish-check FAIL: ")
        assert "unchanged since this failure, so it was not run again" in message
        assert "```output\nboom\n```" in message
        assert len(message) < finish_check.REPORT_CHARACTERS
    write(root / "src.txt", "two\n")
    assert hook("codex", digest, root)[1]["decision"] == "block" and runs() == 2


def test_an_unchanged_tree_that_timed_out_runs_again_only_under_a_longer_timeout(
    tmp_path: Path,
) -> None:
    """Breaks if a timed-out tree is run again, the limit spent, at every turn end, or if
    raising the timeout cannot get the same tree checked."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; sleep 3"])
    short = finish_check.MARGIN_SECONDS + 1

    def runs() -> int:
        return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0

    first = hook("codex", digest, root, timeout=short)[1]["systemMessage"]
    assert first.startswith("finish-check UNVERIFIED: ") and runs() == 1
    again = hook("codex", digest, root, timeout=short)[1]["systemMessage"]
    assert again.startswith("finish-check UNVERIFIED: ") and runs() == 1
    assert "Not run again: the working tree is unchanged since that check." in again
    longer = hook("codex", digest, root, timeout=short + 10)[1]["systemMessage"]
    assert longer.startswith("finish-check PASS: ") and runs() == 2


@pytest.mark.parametrize(
    ("line", "code"),
    [
        ("no-such-tool-here --check", 127),
        pytest.param(
            "./not-executable",
            126,
            marks=pytest.mark.skipif(
                WINDOWS, reason="Git's shell on Windows runs any file that starts with `#!`"
            ),
            id="./not-executable-126",
        ),
    ],
)
def test_a_command_the_hooks_environment_cannot_run_is_unverified_and_holds_nothing(
    tmp_path: Path, line: str, code: int
) -> None:
    """Breaks if a tool missing from the hook's PATH, or a file that cannot be executed, holds
    the finish as a failure the agent's change caused."""

    external = tmp_path / "not-executable"
    if code == 126:
        line = q(external)
    root, digest = target(tmp_path / "t", [line])
    write(external, "#!/bin/sh\nexit 0\n")

    _, verdict = hook("codex", digest, root)

    assert list(verdict) == ["systemMessage"]
    message = verdict["systemMessage"]
    assert message.startswith("finish-check UNVERIFIED:")
    assert "could not run in the hook's environment" in message
    assert f"exit {code} after " in message
    # Not remembered: once the environment is fixed, the same tree runs again.
    external.chmod(0o755)
    if code == 127:
        assert hook("codex", digest, root)[1]["systemMessage"].startswith(
            "finish-check UNVERIFIED: `no-such-tool-here --check` could not run"
        )
    else:
        assert hook("codex", digest, root)[1]["systemMessage"].startswith("finish-check PASS: ")


@pytest.mark.parametrize(
    ("files", "line", "tool"),
    [
        pytest.param(
            {"Makefile": "test:\n\tno-such-tool-here --check\n"},
            "make test",
            "no-such-tool-here",
            id="make",
        ),
        pytest.param(
            {"run.sh": "#!/bin/sh\nno-such-tool-here --check || exit 2\n"},
            "sh run.sh",
            "no-such-tool-here",
            id="script",
        ),
        pytest.param(
            {},
            f"{q(sys.executable)} -m no_such_module_here",
            "python -m no_such_module_here",
            id="module",
        ),
    ],
)
def test_a_runner_that_cannot_find_its_tool_is_unverified_and_holds_nothing(
    tmp_path: Path, files: dict[str, str], line: str, tool: str
) -> None:
    """Breaks if a tool missing from the hook's PATH holds the finish as a failure when a runner
    between the hook and the tool (make, a script, a Python launcher) exits with its own code."""

    if line.startswith("make") and shutil.which("make") is None:
        pytest.skip("make is not installed here")
    root, digest = target(tmp_path / "t", [line])
    for name, text in files.items():
        write(root / name, text)

    _, verdict = hook("codex", digest, root)

    assert list(verdict) == ["systemMessage"]
    message = verdict["systemMessage"]
    assert message.startswith("finish-check UNVERIFIED: "), message
    assert "could not run in the hook's environment" in message
    assert f"`{tool}` is not on this PATH" in message


WINDOWS_MAKE = (
    "nosuchtool-zz --version\r\n"
    "process_begin: CreateProcess(NULL, nosuchtool-zz --version, ...) failed.\r\n"
    "make (e=2): {sentence}\r\n"
    "make: *** [D:\\a\\_temp/probe.mk:2: all] Error 2\r\n"
)


@pytest.mark.parametrize(
    "sentence",
    ["The system cannot find the file specified.", "Das System kann die Datei nicht finden."],
)
def test_gnu_make_on_windows_says_a_missing_tool_by_its_error_code(sentence: str) -> None:
    """Breaks if the two-line form GNU make prints on Windows (observed on a hosted Windows
    runner, 2026-10-06) is not read as a missing tool, or is read by its localized sentence."""

    output = WINDOWS_MAKE.format(sentence=sentence).encode()

    assert finish_check.missing_tool(output) == "nosuchtool-zz"
    assert not finish_check.other_failure(output)
    other = output.replace(b"e=2", b"e=5")
    assert finish_check.missing_tool(other) is None
    ran = b"ran something\r\n" + output
    assert finish_check.missing_tool(ran) is None


@pytest.mark.parametrize("recipe", ["pytest", "pytest -q"])
@pytest.mark.parametrize("echoed", [True, False])
def test_gnu_make_on_windows_reads_a_recipe_of_one_word_or_more(recipe: str, echoed: bool) -> None:
    """Breaks if the `CreateProcess` line of a one-word recipe, which has a comma straight after
    the tool, names the tool with the comma or reads as output that ran before it."""

    output = (
        (f"{recipe}\r\n" if echoed else "")
        + f"process_begin: CreateProcess(NULL, {recipe}, ...) failed.\r\n"
        + "make (e=2): The system cannot find the file specified.\r\n"
        + "make: *** [probe.mk:2: all] Error 2\r\n"
    ).encode()

    assert finish_check.missing_tool(output) == "pytest"
    assert not finish_check.other_failure(output)


def test_a_missing_tool_line_that_names_a_path_that_is_there_still_fails(tmp_path: Path) -> None:
    """Breaks if a Done that prints make's not-found line, or the CreateProcess form, for a tool
    named by a path that is a file reads as absent, so that a fabricated line could excuse it."""

    root = tmp_path / "project"
    (root / "bin").mkdir(parents=True)
    write(root / "bin/tool", "#!/bin/sh\nexit 0\n")
    absolute = str(root / "bin/tool")
    for named in (absolute, "bin/tool"):
        made = f"make: {named}: No such file or directory\n".encode()
        created = (
            f"process_begin: CreateProcess(NULL, {named} -q, ...) failed.\n"
            "make (e=2): The system cannot find the file specified.\n"
        ).encode()
        for line in (made, created):
            assert not finish_check.confirmed_absent(root, line, {"PATH": "/nowhere"}), line
    gone = b"make: bin/none: No such file or directory\n"
    assert finish_check.confirmed_absent(root, gone, {"PATH": "/nowhere"})


def test_the_absence_check_looks_with_the_path_extensions_and_system_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the lookup that confirms a tool absent drops `PATHEXT` or `SYSTEMROOT`, so that
    on Windows a tool found only through an extension the machine adds reads as absent."""

    seen: list[dict[str, str]] = []

    def find(name: str, environment: dict[str, str], **_: bool) -> None:
        seen.append(dict(environment))

    monkeypatch.setattr(finish_check.programs, "find", find)
    line = b"make: npm: No such file or directory\n"
    environment = {"PATH": "/nowhere", "Pathext": ".EXE;.PY", "SYSTEMROOT": "C:\\Windows", "X": "1"}

    assert finish_check.confirmed_absent(tmp_path, line, environment)

    assert seen[0]["Pathext"] == ".EXE;.PY" and seen[0]["SYSTEMROOT"] == "C:\\Windows"
    assert "X" not in seen[0]


@pytest.mark.parametrize(
    "printed",
    [
        "FileNotFoundError: [Errno 2] No such file or directory: 'fixtures/x.json'",
        "E   ModuleNotFoundError: No module named 'missing_dependency'",
        "lookup: user not found",
    ],
)
def test_a_tests_own_not_found_message_still_holds(tmp_path: Path, printed: str) -> None:
    """Breaks if a failing test whose output ends with its own not-found message reads as a tool
    the hook's environment lacks, and so holds nothing."""

    root, digest = target(tmp_path / "t", [f"echo {shlex.quote(printed)}; exit 1"])

    _, verdict = hook("codex", digest, root)

    assert verdict.get("decision") == "block", verdict


def test_measuring_runs_without_the_projects_and_a_virtual_environments_path(
    tmp_path: Path,
) -> None:
    """Breaks if adopt measures Done with a PATH entry inside the project or a virtual
    environment's bin, which a desktop harness's hook does not have, so the record says PASS
    and every turn end then fails."""

    root = tmp_path / "project"
    (root / ".venv" / "bin").mkdir(parents=True)
    elsewhere = tmp_path / "other-venv"
    (elsewhere / "bin").mkdir(parents=True)
    write(elsewhere / "pyvenv.cfg", "home = /usr/bin\n")
    path = os.pathsep.join([str(root / ".venv" / "bin"), str(elsewhere / "bin"), "/usr/bin"])

    environment, dropped = finish_check.hook_environment(
        root, {"PATH": path, "VIRTUAL_ENV": str(elsewhere), "LANG": "C.UTF-8"}
    )

    assert environment["PATH"] == "/usr/bin"
    assert "VIRTUAL_ENV" not in environment and environment["LANG"] == "C.UTF-8"
    assert dropped == (str(root / ".venv" / "bin"), str(elsewhere / "bin"))


def test_a_windows_mapping_keeps_one_filtered_path_and_no_virtual_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a Mapping with Windows' mixed-case keys keeps the project PATH, gains
    a second PATH key or retains VIRTUAL_ENV. Real os.environ already normalizes these keys."""

    root = tmp_path / "project"
    local = root / ".venv" / "Scripts"
    local.mkdir(parents=True)
    system = tmp_path / "system"
    system.mkdir()
    environment = {
        "Path": os.pathsep.join([str(local), str(system)]),
        "Virtual_Env": str(root / ".venv"),
        "LANG": "C.UTF-8",
    }

    with monkeypatch.context() as patch:
        patch.setattr(finish_check.os, "name", "nt")
        filtered, dropped = finish_check.hook_environment(root, environment)

    assert filtered == {"PATH": str(system), "LANG": "C.UTF-8"}
    assert dropped == (str(local),)


def test_a_virtual_environments_scripts_folder_is_left_out_as_its_bin_folder_is(
    tmp_path: Path,
) -> None:
    """Breaks if the measurement leaves out only a folder named `bin`: a virtual environment on
    Windows keeps its programs in `Scripts`, whose parent holds `pyvenv.cfg` as `bin`'s does, and
    the rule is that parent, not the name. The folder is laid out here on any platform."""

    root = tmp_path / "project"
    root.mkdir()
    venv = tmp_path / "windows-venv"
    (venv / "Scripts").mkdir(parents=True)
    write(venv / "pyvenv.cfg", "home = C:/Python\n")
    system = tmp_path / "system"
    system.mkdir()

    environment, dropped = finish_check.hook_environment(
        root, {"PATH": os.pathsep.join([str(venv / "Scripts"), str(system)])}
    )

    assert dropped == (str(venv / "Scripts"),)
    assert environment["PATH"] == str(system)


GIT_IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def test_a_project_script_or_module_the_change_removed_still_holds(tmp_path: Path) -> None:
    """Breaks if a script or a module of the project that the change removed reads as a tool the
    hook's environment lacks, so a broken Done reaches the person and not the agent."""

    if shutil.which("make") is None:
        pytest.skip("make is not installed here")
    done = ["make test", f"{q(sys.executable)} -m mypkg"]
    root, digest = target(tmp_path / "t", done)
    write(root / "Makefile", "test:\n\t./scripts/lint.sh\n")
    (root / "scripts").mkdir()
    write(root / "scripts/lint.sh", "#!/bin/sh\nexit 0\n")
    (root / "scripts/lint.sh").chmod(0o755)
    (root / "mypkg").mkdir()
    write(root / "mypkg/__main__.py", "")
    write(root / "mypkg/__init__.py", "")
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
    subprocess.run([GIT, "-C", str(root), *GIT_IDENTITY, "commit", "-qm", "tools"], check=True)
    (root / "scripts/lint.sh").unlink()

    _, verdict = hook("codex", digest, root)

    assert verdict.get("decision") == "block", verdict
    assert finish_check.project_owned(root, "python -m mypkg")
    shutil.rmtree(root / "mypkg")
    assert finish_check.project_owned(root, "python -m mypkg"), "HEAD still holds it"
    assert not finish_check.project_owned(root, "python -m pytest")
    assert not finish_check.project_owned(root, "pytest")
    assert not finish_check.project_owned(root, "/opt/tool/bin/pytest")
    assert finish_check.project_owned(root, str(root / "scripts/lint.sh")), "absolute, inside"
    (root / "bin").mkdir()
    write(root / "bin/mytool", "#!/bin/sh\nexit 0\n")
    (root / "ns").mkdir()
    write(root / "ns/check.py", "")
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
    # The mode is Git's own, so it holds on a file system with no execute bit.
    subprocess.run([GIT, "-C", str(root), "add", "--chmod=+x", "bin/mytool"], check=True)
    subprocess.run([GIT, "-C", str(root), *GIT_IDENTITY, "commit", "-qm", "more"], check=True)
    (root / "bin/mytool").unlink()
    shutil.rmtree(root / "ns")
    assert finish_check.project_owned(root, "mytool"), "a tracked executable the change removed"
    assert finish_check.project_owned(root, "python -m ns.check"), "a namespace package"


@pytest.mark.parametrize(
    ("output", "tool"),
    [
        (
            "make[1]: pytest: No such file or directory\nmake[1]: *** [test] Error 1\n"
            "make[1]: Leaving directory '/w/sub'\nmake: *** [all] Error 2\n",
            "pytest",
        ),
        ("/bin/sh: pytest: command not found\n", "pytest"),
        ("run.sh: line 3: pytest: command not found\n", "pytest"),
        ("run.sh: 3: pytest: not found\n", "pytest"),
        ("/usr/bin/python3: No module named pytest\n", "python -m pytest"),
        ("1 failed in 0.2s\n", None),
    ],
)
def test_the_missing_tool_forms(output: str, tool: str | None) -> None:
    """Breaks if a runner's not-found line is missed after make's own lines, or a form is read
    that names no tool."""

    assert finish_check.missing_tool(output.encode()) == tool


def test_a_tool_found_only_on_a_dropped_entry_is_not_kept_as_a_known_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a Done that passes only with the virtual environment's bin on PATH, while a
    same-named tool elsewhere on PATH fails, is kept as a known failure that hides later ones."""

    done = ["faketool"]
    root, _ = target(tmp_path / "t", done)
    venv = root / ".venv/bin"
    venv.mkdir(parents=True)
    write(venv / "faketool", "#!/bin/sh\nexit 0\n")
    other = tmp_path / "other/bin"
    other.mkdir(parents=True)
    write(other / "faketool", "#!/bin/sh\necho 'ERROR tests/x.py::t'\nexit 2\n")
    for tool in (venv / "faketool", other / "faketool"):
        tool.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv), str(other), *system_path()]))

    measured = finish_check.measure(root, done, 600)

    (result,) = measured.results
    assert result.verdict == finish_check.UNVERIFIED, result
    assert str(venv) in result.note and measured.dropped == (str(venv),)
    record = finish_check.known_record(root, finish_check.done_digest(done))
    assert record is None or not record.failing


def test_the_install_report_names_the_entries_the_measurement_left_out(tmp_path: Path) -> None:
    """Breaks if the person is not told that Done was measured without part of their PATH."""

    from outcomebound_tools import adopt

    measured = finish_check.Measured((), 0.0, False, dropped=("/p/.venv/bin",))
    notes = adopt.measured_notes(tmp_path, measured, 600)
    assert ("note", notes[0][1]) == notes[0] and "/p/.venv/bin" in notes[0][1]


@pytest.mark.parametrize(
    ("files", "line"),
    [
        pytest.param(
            {},
            "printf 'FAILED tests/a.py::t\\n1 failed in 0.1s\\n'; no-such-tool-here; exit 2",
            id="compound",
        ),
        pytest.param(
            {"Makefile": "a:\n\tfalse\nb:\n\tno-such-tool-here\n"},
            "make -k a b",
            id="make-k",
        ),
        pytest.param(
            {},
            f"{q(sys.executable)} -c 'assert 1 == 2'; no-such-tool-here; exit 2",
            id="traceback",
        ),
        pytest.param(
            {}, "printf 'FAILED tests/a.py::t\\n'; no-such-tool-here", id="exit-127-after-failure"
        ),
    ],
)
def test_a_missing_tool_after_another_failure_still_holds(
    tmp_path: Path, files: dict[str, str], line: str
) -> None:
    """Breaks if a missing tool at the end of a command hides a failure earlier in it: a failed
    test before it, or another make target that failed under `make -k`."""

    if "make" in line and shutil.which("make") is None:
        pytest.skip("make is not installed here")
    root, digest = target(tmp_path / "t", [line])
    for name, text in files.items():
        write(root / name, text)

    _, verdict = hook("codex", digest, root)

    assert verdict.get("decision") == "block", verdict


def test_a_rerun_that_fails_another_way_keeps_no_known_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a command that fails one way without the virtual environment's bin and another
    way with it is kept as a known failure, which would hide a later regression."""

    done = ["faketool"]
    root, _ = target(tmp_path / "t", done)
    venv = root / ".venv/bin"
    venv.mkdir(parents=True)
    write(venv / "faketool", "#!/bin/sh\necho 'FAILED tests/b.py::t'\nexit 2\n")
    other = tmp_path / "other/bin"
    other.mkdir(parents=True)
    write(other / "faketool", "#!/bin/sh\necho 'FAILED tests/a.py::t'\nexit 2\n")
    for tool in (venv / "faketool", other / "faketool"):
        tool.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv), str(other), *system_path()]))

    measured = finish_check.measure(root, done, 600)

    (result,) = measured.results
    assert result.verdict == finish_check.UNVERIFIED and "runs differently" in result.note
    record = finish_check.known_record(root, finish_check.done_digest(done))
    assert record is None or not record.failing


def test_empty_and_relative_path_entries_name_folders_of_the_target(tmp_path: Path) -> None:
    """Breaks if an empty PATH entry (the current folder) or a relative one is kept, though Done
    runs from the target's root, so they name the target's own folders."""

    root = tmp_path / "project"
    root.mkdir()
    path = os.pathsep.join(["", "bin", "/usr/bin"])

    environment, dropped = finish_check.hook_environment(root, {"PATH": path})

    assert environment["PATH"] == "/usr/bin" and dropped == ("", "bin")


def test_a_record_says_whether_it_was_measured_as_a_hook_runs_done() -> None:
    """Breaks if a record an older engine wrote, with the agent's PATH, reads as measured as a
    hook runs Done, or a new record loses that mark."""

    tree = "a" * 40
    old = {"done": "b" * 64, "prefix": "", "head": tree, "measured": "2026-10-05", "seconds": 1.0}
    old_text = json.dumps({"records": [{**old, "failing": {}}]})
    new_text = json.dumps({"records": [{**old, "failing": {}, "as_hook": True}]})
    (older,) = finish_check.parse_known(old_text) or []
    (newer,) = finish_check.parse_known(new_text) or []
    assert not older.as_hook and newer.as_hook
    assert newer.document()["as_hook"] is True


def test_a_not_found_line_the_command_prints_itself_still_holds(tmp_path: Path) -> None:
    """Breaks if a command that prints a runner's not-found line for a tool that is on the PATH
    reads as a tool the hook's environment lacks: the exemption is for an absent tool, not for a
    line of that shape."""

    for line in (
        "echo 'make: sh: No such file or directory'; exit 2",
        "echo '/no/such/bin/python3: No module named pytest'; exit 2",
    ):
        root, digest = target(tmp_path / str(len(line)), [line])

        _, verdict = hook("codex", digest, root)

        assert verdict.get("decision") == "block", (line, verdict)


@pytest.mark.parametrize("failure", ["timeout", "oserror"])
def test_an_unreadable_module_probe_does_not_excuse_a_failed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Breaks if a failed confirmation probe turns a command's failure into an unheld
    environment verdict, even though the probe established no module was absent."""

    printed = f"{Path(sys.executable).as_posix()}: No module named no_such_module_here"
    line = f"echo {shlex.quote(printed)}; exit 2"
    root, _ = target(tmp_path / "t", [line])
    original = subprocess.run

    def probe(argv: list[str], **options: Any) -> subprocess.CompletedProcess[bytes]:
        if Path(argv[0]) == Path(sys.executable) and argv[1] == "-c":
            if failure == "timeout":
                raise subprocess.TimeoutExpired(argv, options["timeout"])
            raise OSError("probe could not start")
        return original(argv, **options)

    monkeypatch.setattr(finish_check.subprocess, "run", probe)

    result = finish_check.run_one(root, line, 60)
    verdict = finish_check.verdict_for([result], True, root, 60)

    assert (result.verdict, result.code) == (finish_check.FAIL, 2), result
    assert verdict.get("decision") == "block", verdict


@pytest.mark.parametrize(
    ("seconds", "probe_limit"),
    [(1.0, 0.75), (0.1, None), (None, 30.0)],
)
def test_a_module_probe_uses_only_time_left_after_the_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seconds: float | None,
    probe_limit: float | None,
) -> None:
    """Breaks if confirming a missing module spends another thirty seconds after the
    command's time allowance, or starts after the hook's deadline."""

    now = [100.0]
    limits: list[float] = []
    printed = f"{Path(sys.executable).as_posix()}: No module named no_such_module_here"

    class Finished:
        def wait(self, timeout: float | None = None) -> int:
            now[0] = 100.25
            return 2

    def start(argv: list[str], **options: Any) -> Finished:
        options["stdout"].write((printed + "\n").encode())
        return Finished()

    def probe(argv: list[str], **options: Any) -> subprocess.CompletedProcess[bytes]:
        limits.append(options["timeout"])
        return subprocess.CompletedProcess(argv, 3)

    monkeypatch.setattr(finish_check.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(finish_check.programs, "posix_shell", lambda *a, **k: "/bin/sh")
    monkeypatch.setattr(finish_check, "project_owned", lambda *a: False)
    # The command's start is faked where `run_one` makes it, `programs.start_tree`: a fake
    # `Popen` would be joined to a job and resumed on Windows, and this one is no process.
    monkeypatch.setattr(finish_check.programs, "start_tree", start)
    monkeypatch.setattr(finish_check.subprocess, "run", probe)

    result = finish_check.run_one(tmp_path, "module check", seconds)

    assert limits == ([] if probe_limit is None else [probe_limit])
    expected = finish_check.FAIL if probe_limit is None else finish_check.UNVERIFIED
    assert (result.verdict, result.code) == (expected, 2), result


def test_a_module_is_the_projects_only_at_its_root_or_under_src(tmp_path: Path) -> None:
    """Breaks if a folder deep in the tree that shares a module's name makes a missing
    third-party module read as the project's own."""

    root, _ = target(tmp_path / "t", ["true"])
    (root / "docs/pytest").mkdir(parents=True)
    write(root / "docs/pytest/notes.md", "x\n")
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
    subprocess.run([GIT, "-C", str(root), *GIT_IDENTITY, "commit", "-qm", "docs"], check=True)

    assert not finish_check.project_owned(root, "python -m pytest")


def test_the_absence_check_reads_a_relative_path_entry_from_the_target(tmp_path: Path) -> None:
    """Breaks if a relative PATH entry is read from the engine's own folder, though Done runs
    from the target's root, so a tool in the target's `bin` reads absent."""

    root = tmp_path / "project"
    (root / "bin").mkdir(parents=True)
    write(root / "bin/mytool", "#!/bin/sh\nexit 0\n")
    (root / "bin/mytool").chmod(0o755)
    line = b"run.sh: line 3: mytool: command not found\n"

    assert not finish_check.confirmed_absent(root, line, {"PATH": "bin"})
    assert finish_check.confirmed_absent(root, line, {"PATH": "/nowhere"})


def test_a_record_1_0_0_wrote_reads_as_a_pass_and_an_unreadable_one_as_none() -> None:
    """Breaks if an install upgraded from 1.0.0 reruns or misreads the pass it remembered, or if
    a damaged record is trusted as a verdict."""

    tree = "a" * 64
    assert finish_check.parse_checked(tree + "\n") == finish_check.Checked(
        tree, finish_check.DEFAULT_TIMEOUT, finish_check.PASS
    )
    for text in (
        "",
        "not json",
        '{"tree": "x"}',
        json.dumps({"tree": tree, "timeout": 600, "verdict": "FAIL", "results": []}),
    ):
        assert finish_check.parse_checked(text) is None


def test_two_targets_in_one_repository_never_share_a_pass(tmp_path: Path) -> None:
    """Breaks if a pass remembered for one target lets another in the same repository skip."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])
    inner = root / "inner"
    (inner / ".outcomebound").mkdir(parents=True)
    shutil.copy(root / ".outcomebound/manifest.json", inner / ".outcomebound/manifest.json")
    (inner / "deeper").mkdir()
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
    subprocess.run([GIT, "-C", str(root), *identity, "commit", "-qm", "inner"], check=True)

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"]
    assert "PASS" in hook("codex", digest, root, cwd=inner / "deeper")[1]["systemMessage"]
    assert len(count.read_text(encoding="utf-8").splitlines()) == 2


def test_a_tree_the_commands_changed_is_not_remembered_as_passed(tmp_path: Path) -> None:
    """Breaks if the tree a formatter or a concurrent edit left behind is cached as checked."""

    root, digest = target(tmp_path / "t", ["echo again >> grows.txt"])

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"]
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"]
    assert len((root / "grows.txt").read_text(encoding="utf-8").splitlines()) == 2


@posix_only
@pytest.mark.parametrize("name", ["check.sh", "denied check.sh"])
def test_a_script_that_loses_its_execute_bit_is_checked_again(tmp_path: Path, name: str) -> None:
    """Breaks if a pass cached for an untracked script survives the script becoming unrunnable."""

    line = "./" + q(name)
    root, digest = target(tmp_path / "t", [line])
    script = root / name
    write(script, "#!/bin/sh\nexit 0\n")
    script.chmod(0o755)

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"]
    script.chmod(0o644)
    verdict = hook("codex", digest, root)[1]
    assert verdict["decision"] == "block"
    assert f"FAIL {line}: exit 126" in verdict["reason"]


@pytest.mark.skipif(
    os.name == "nt",
    reason="os.kill ends the process it names on Windows, here the test's own, and `$$` is an "
    "MSYS process id, which os.kill would read as a Windows one",
)
@pytest.mark.parametrize("number", [signal.SIGINT, signal.SIGTERM])
def test_a_stop_that_arrives_while_a_command_starts_stops_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, number: int
) -> None:
    """Breaks if Ctrl-C, or SIGTERM where adopt maps it, that arrives after the command has
    started but before `subprocess.Popen` returns leaves the command running with no process
    left to stop it: the signal is sent from inside `Popen`, once the command has written its
    pid."""

    pid = tmp_path / "pid"
    real = subprocess.Popen

    def late(*arguments: Any, **options: Any) -> subprocess.Popen[bytes]:
        process = real(*arguments, **options)
        deadline = time.monotonic() + 30
        while not (pid.exists() and pid.read_text(encoding="utf-8").strip()):
            assert time.monotonic() < deadline, "the command never wrote its pid"
            time.sleep(0.01)
        os.kill(os.getpid(), number)
        return process

    class Stop(Exception):
        pass

    def stop(got: int, frame: object) -> None:
        raise Stop(got)

    # SIGINT at Python's default, as a terminal's foreground job has it: a suite started as a
    # background job of a shell has SIGINT ignored, and an ignored signal is left ignored.
    previous = {
        signal.SIGINT: signal.signal(signal.SIGINT, signal.default_int_handler),
        signal.SIGTERM: signal.signal(signal.SIGTERM, stop),
    }
    monkeypatch.setattr(finish_check.subprocess, "Popen", late)
    try:
        with pytest.raises((KeyboardInterrupt, Stop)):
            finish_check.run_one(tmp_path, f"echo $$ > {pid}; exec sleep 300", None)
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
        assert signal.getsignal(signal.SIGTERM) is stop
    finally:
        for got, handler in previous.items():
            signal.signal(got, handler)
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid.read_text(encoding="utf-8")), 0)


def test_a_command_is_not_started_once_the_limit_has_passed(tmp_path: Path) -> None:
    """Breaks if a Done command starts with no time left, to be cut off by the harness."""

    marker = tmp_path / "ran"
    results = finish_check.run_all(tmp_path, [f"touch {marker}"], time.monotonic() - 1)
    assert [(r.verdict, r.why, r.cause) for r in results] == [
        (finish_check.UNVERIFIED, "not started: the time limit had passed", finish_check.TIME)
    ]
    assert not marker.exists()


def test_the_held_report_sends_the_agent_on_with_the_work_a_failure_does_not_block(
    tmp_path: Path,
) -> None:
    """Breaks if the hold tells the agent to fix a failure it did not cause or one outside its
    authority, or to end its turn on such a failure instead of continuing with the rest."""

    root, digest = target(tmp_path / "t", ["exit 1"])
    reason = hook("codex", digest, root)[1]["reason"]
    assert "Fix what your change broke and continue with the work." in reason
    assert (
        "If it failed before your change, a tool it needs is missing here, or the fix needs an "
        "act outside your authority, say so in your report and continue with the work it does "
        "not block."
    ) in reason
    assert "End your turn only when your work is done." in reason


def test_a_long_run_of_backticks_keeps_the_report_under_the_limit(tmp_path: Path) -> None:
    """Breaks if output can widen the report's own fence past the 4,000-character bound."""

    printer = f"{q(sys.executable)} -c 'print(chr(96) * 10000)'; echo last; exit 1"
    root, digest = target(tmp_path / "t", [printer])

    reason = hook("codex", digest, root)[1]["reason"]
    assert len(reason) < finish_check.REPORT_CHARACTERS
    assert "[10000 backticks]" in reason and reason.endswith("last\n```")


def test_a_pass_too_near_the_limit_is_reported_and_not_remembered(tmp_path: Path) -> None:
    """Breaks if reading the tree again and remembering it can run past their own deadline:
    with the time left for them already spent, the pass is reported and the next turn end runs
    again."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"sleep 1; echo run >> {q(count)}"])
    program = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from outcomebound_tools import finish_check as f; "
        "f.REMEMBER_SECONDS = -15.5; "
        "sys.exit(f.main(sys.argv[2:]))"
    )
    for _ in range(2):
        done = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                program,
                str(ROOT),
                "--harness",
                "codex",
                "--done",
                digest,
                "--timeout",
                str(finish_check.MARGIN_SECONDS + 16),
            ],
            input=json.dumps(INPUT["codex"]).encode(),
            cwd=root,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert done.returncode == 0, done.stderr
        assert json.loads(done.stdout)["systemMessage"].startswith("finish-check PASS: ")
    assert len(count.read_text(encoding="utf-8").splitlines()) == 2
    assert not (root / ".git" / finish_check.STATE).exists()


def test_the_tree_is_not_read_once_its_deadline_has_passed(tmp_path: Path) -> None:
    """Breaks if a Git read or a file's hash can start after the deadline it was given."""

    root, digest = target(tmp_path / "t", ["true"])
    write(root / "new.txt", "new\n")
    assert finish_check.tree_digest(root, digest, time.monotonic() - 1) is None
    assert finish_check.tree_digest(root, digest) is not None


def test_a_command_past_the_limit_is_stopped_with_its_group_and_holds_nothing(
    tmp_path: Path,
) -> None:
    """Breaks if a slow check is left for the harness to cut off, if the commands do not stop
    the margin before the entry's own timeout, if a process it started keeps running, or if the
    report offers shortening Done before a longer limit. The commands get the seconds of
    `limit` past the margin, less what the hook's Git reads take before they start: enough that a
    loaded machine still starts the command, and the elapsed seconds the report names are read,
    not assumed."""

    # The command starts a child of its own that outlives it unless the whole tree is stopped: a
    # Python process, so that the pid it records is the platform's own on Windows too.
    holder = (
        "import os, subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "open('child.pid', 'w').write(str(child.pid)); child.wait()"
    )
    write(tmp_path / "holder.py", holder + "\n")
    line = f"{q(sys.executable)} {q(tmp_path / 'holder.py')}"
    root, digest = target(tmp_path / "t", [line])
    limit = 5
    timeout = finish_check.MARGIN_SECONDS + limit
    started = time.monotonic()

    _, verdict = hook("codex", digest, root, cwd=root, timeout=timeout)

    assert time.monotonic() - started < 30
    assert list(verdict) == ["systemMessage"]
    message = verdict["systemMessage"]
    assert message.startswith(
        f"finish-check UNVERIFIED: `{finish_check.shorten(line, 80)}` did not finish within "
        f"{limit} s, {finish_check.MARGIN_SECONDS} s before the hook's {timeout} s timeout"
    )
    assert f"--finish-timeout <seconds>`, for example {2 * timeout}" in message
    assert message.index("--finish-timeout") < message.index("--no-finish-check")
    stopped = re.search(r"stopped at the time limit after (\d+) s", message)
    assert stopped is not None and int(stopped.group(1)) <= limit, message
    if WINDOWS:
        # The report names the path that stopped the tree, so that a grandchild left running
        # says whether the job did not hold it or the job was never used (`taskkill`).
        assert f"stopped at the time limit after {stopped.group(1)} s, by its job" in message
    assert (root / "child.pid").exists(), f"the command never started: {message}"
    child = int((root / "child.pid").read_text(encoding="utf-8"))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and running(child):
        time.sleep(0.1)
    assert not running(child)


@pytest.mark.parametrize("row", ROWS)
def test_no_manifest_names_the_directory_searched_and_holds_nothing(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a hook firing outside an install holds the finish or fails without saying where
    it looked."""

    empty = tmp_path / "empty"
    empty.mkdir()

    _, verdict = hook(row, finish_check.done_digest(["true"]), empty, cwd=empty)

    assert list(verdict) == ["systemMessage"]
    assert f"no .outcomebound/manifest.json found from {empty}" in verdict["systemMessage"]


@pytest.mark.parametrize(
    "arguments",
    [
        ["--harness", "gemini", "--done", "0" * 64],
        ["--harness", "codex", "--done", "short"],
        ["--harness", "codex"],
        ["--harness", "codex", "--done", "0" * 64, "--timeout", "30"],
        ["--harness", "codex", "--done", "0" * 64, "--timeout", "ten"],
    ],
    ids=["unavailable-row", "not-a-digest", "no-digest", "timeout-within-margin", "not-seconds"],
)
def test_a_usage_error_exits_1_never_2(tmp_path: Path, arguments: list[str]) -> None:
    """Breaks if a malformed entry exits 2, which both rows read as holding the finish."""

    done = subprocess.run(
        engine("finish-check", *arguments),
        input=b"{}",
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    assert done.returncode == 1 and done.stdout == b""


# --- known failures: what failed when adopt measured Done -------------------------

IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def failing(root: Path, digest: str) -> dict[str, int]:
    """The exit code of each known failure kept for `root` and this Done digest; a record that
    applies to `root` must be kept."""

    record = finish_check.known_record(root, digest)
    assert record is not None
    return {line: failure.code for line, failure in record.failing.items()}


def runner_script(root: Path, flags: Path) -> str:
    """A Done command that prints a pytest summary line for each flag file in `flags` and exits
    1 where there is any, as a test runner reports its failing tests."""

    script = root / "suite.sh"
    write(
        script,
        "#!/bin/sh\nrc=0\n"
        f'for f in {q(flags)}/*; do [ -e "$f" ] || continue; '
        'echo "FAILED tests/$(basename "$f").py::test_x - AssertionError"; rc=1; done\n'
        'echo "short test summary"; exit $rc\n',
    )
    subprocess.run([GIT, "-C", str(root), "add", "suite.sh"], check=True)
    subprocess.run([GIT, "-C", str(root), *IDENTITY, "commit", "-qm", "suite"], check=True)
    return "sh suite.sh"


def test_a_known_failure_holds_nothing_and_a_new_failure_after_it_holds(tmp_path: Path) -> None:
    """Breaks if a failure that was there when Done was measured holds every changed tree, if a
    command after it is skipped, or if a new failure in another command does not hold, with its
    own output shown and the known one named as such."""

    broken = tmp_path / "broken"
    done = ["echo old; exit 1", f"test ! -e {q(broken)} || {{ echo new; exit 4; }}"]
    root, digest = target(tmp_path / "t", done)
    measured = finish_check.measure(root, done, 600)
    assert measured.kept and [r.verdict for r in measured.results] == ["FAIL", "PASS"]

    write(root / "src.txt", "two\n")
    verdict = hook("codex", digest, root)[1]
    assert list(verdict) == ["systemMessage"]
    message = verdict["systemMessage"]
    assert message.startswith("finish-check FAIL, known: ")
    assert "(known by its exit code only, since its output names no failure ids; not held)" in (
        message
    )
    assert "a new failure inside it is not told apart" in message
    assert f"PASS {finish_check.shorten(done[1])}" in message

    write(broken, "")
    write(root / "src.txt", "three\n")
    reason = hook("codex", digest, root)[1]["reason"]
    assert "FAIL echo old; exit 1: exit 1 after " in reason and "; not held)" in reason
    assert f"FAIL {finish_check.shorten(done[1])}: exit 4 after " in reason
    assert "A command marked known failed the same way before your change" in reason
    assert reason.endswith("```output\nnew\n```")


def test_a_new_failing_test_inside_a_known_command_holds(tmp_path: Path) -> None:
    """Breaks if a known command hides a test that newly fails inside it with the same exit
    code: its failure ids must be among those adopt measured. An old failing test alone still
    holds nothing."""

    flags = tmp_path / "flags"
    flags.mkdir()
    write(flags / "test_old", "")
    root, _ = target(tmp_path / "t", ["true"])
    done = [runner_script(root, flags)]
    manifest = root / ".outcomebound/manifest.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["artifacts"][0]["done"] = done
    write(manifest, json.dumps(document))
    digest = finish_check.done_digest(done)
    finish_check.measure(root, done, 600)
    record = finish_check.known_record(root, digest)
    assert record is not None
    assert record.failing[done[0]].ids == {"pytest tests/test_old.py::test_x"}

    write(root / "src.txt", "two\n")
    message = hook("codex", digest, root)[1]["systemMessage"]
    assert (
        message.startswith("finish-check FAIL, known: ") and "known by its failure ids" in message
    )

    write(flags / "test_new", "")
    write(root / "src.txt", "three\n")
    reason = hook("codex", digest, root)[1]["reason"]
    assert "not known: new failure ids pytest tests/test_new.py::test_x" in reason
    assert "FAILED tests/test_new.py::test_x" in reason


def test_a_new_parametrized_case_with_a_space_in_its_id_holds(tmp_path: Path) -> None:
    """Breaks if a pytest id is cut at its first space, which makes `test_x[hello mars]` the
    known `test_x[hello world]` and hides the new failure."""

    lines = tmp_path / "lines"
    write(lines, "FAILED tests/test_x.py::test_x[hello world] - assert 0\n")
    done = [f"cat {q(lines)}; exit 1"]
    root, digest = target(tmp_path / "t", done)
    finish_check.measure(root, done, 600)

    with lines.open("ab") as handle:
        handle.write(b"FAILED tests/test_x.py::test_x[hello mars] - assert 1\n")
    write(root / "src.txt", "two\n")
    reason = hook("codex", digest, root)[1]["reason"]
    assert "new failure ids pytest tests/test_x.py::test_x[hello mars]" in reason


def test_a_measurement_that_replaces_a_record_names_what_it_adds(tmp_path: Path) -> None:
    """Breaks if a measurement made after a change breaks code makes that failure known without
    naming it apart from the failures the replaced record held."""

    lines = tmp_path / "lines"
    write(lines, "FAILED tests/test_a.py::test_old - assert 0\n")
    done = [f"cat {q(lines)}; exit 1", "true"]
    root, _ = target(tmp_path / "t", done)
    first = finish_check.measure(root, done, 600)
    assert first.previous is None and first.added == ()

    with lines.open("ab") as handle:
        handle.write(b"FAILED tests/test_a.py::test_new - assert 1\n")
    second = finish_check.measure(root, done, 600)
    assert second.previous is not None
    shown = finish_check.shorten(done[0], 80)
    assert second.added == (f"`{shown}`: pytest tests/test_a.py::test_new",)
    message = hook("codex", finish_check.done_digest(done), root)[1]["systemMessage"]
    assert f"on commit {second.previous.head[:12]}, which this checkout descends from" in message


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("FAILED tests/a.py::test_b - assert 1", "pytest tests/a.py::test_b"),
        ("ERROR tests/a.py - ImportError", "pytest tests/a.py"),
        ("FAILED tests/a.py::t[hello world] - assert 0", "pytest tests/a.py::t[hello world]"),
        ("FAILED tests/a.py::t[hello world]", "pytest tests/a.py::t[hello world]"),
        ("FAIL: test_x (pkg.tests.T)", "unittest test_x (pkg.tests.T)"),
        ("FAIL: test_x (pkg.tests.T) (i=1)", "unittest test_x (pkg.tests.T) (i=1)"),
        ("    --- FAIL: TestThing (0.00s)", "go TestThing"),
        ("test tests::it_works ... FAILED", "cargo tests::it_works"),
        ("  \u2715 adds numbers (5 ms)", "jest adds numbers"),
        (" \u00d7 src/a.test.ts > sum 3ms", "jest src/a.test.ts > sum"),
        ("make: *** [Makefile:4: test] Error 1", "make Makefile:4: test"),
        ("make[1]: *** [check] Error 2", "make check"),
    ],
)
def test_each_runner_names_its_failures_by_id(line: str, found: str) -> None:
    """Breaks if a runner's own failure line is not read as an id, or a timing in it is kept,
    which would make the same failure a new id at each run."""

    assert finish_check.failure_ids(f"noise\n{line}\n12 failed in 3.2s\n".encode()) == {found}


def test_a_known_command_failing_with_another_exit_code_holds(tmp_path: Path) -> None:
    """Breaks if a command known to fail hides a different failure of it, read by exit code."""

    code = tmp_path / "code"
    write(code, "1")
    done = [f'exit "$(cat {q(code)})"']
    root, digest = target(tmp_path / "t", done)
    finish_check.measure(root, done, 600)

    write(code, "2")
    write(root / "src.txt", "two\n")
    assert hook("codex", digest, root)[1]["decision"] == "block"


def test_a_known_failure_that_passes_leaves_the_record_and_holds_when_it_fails_again(
    tmp_path: Path,
) -> None:
    """Breaks if a known failure, once fixed, can break again without a hold: the record would
    then hide a failure the change caused."""

    flag = tmp_path / "flag"
    write(flag, "")
    done = [f"test ! -e {q(flag)}"]
    root, digest = target(tmp_path / "t", done)
    finish_check.measure(root, done, 600)
    assert failing(root, digest) == {done[0]: 1}

    flag.unlink()
    write(root / "src.txt", "two\n")
    assert hook("codex", digest, root)[1]["systemMessage"].startswith("finish-check PASS: ")
    assert failing(root, digest) == {}

    write(flag, "")
    write(root / "src.txt", "three\n")
    assert hook("codex", digest, root)[1]["decision"] == "block"


def test_known_failures_are_shared_by_worktrees_and_kept_for_one_done_list(tmp_path: Path) -> None:
    """Breaks if a worktree of the repository holds on a failure measured in its main checkout,
    or if the record applies to a Done list it was not measured for."""

    done = ["echo old; exit 1"]
    root, digest = target(tmp_path / "t", done)
    finish_check.measure(root, done, 600)
    tree = tmp_path / "wt"
    subprocess.run([GIT, "-C", str(root), "worktree", "add", "-q", str(tree)], check=True)

    write(tree / "src.txt", "two\n")
    message = hook("codex", digest, tree)[1]["systemMessage"]
    assert message.startswith("finish-check FAIL, known: ")
    assert finish_check.known_record(root, finish_check.done_digest(["make test"])) is None


def test_a_record_measured_on_another_branch_does_not_apply(tmp_path: Path) -> None:
    """Breaks if a failure measured on one branch is known in a worktree whose history does not
    hold that commit: there the failure may be the change's own, so it must hold."""

    flag = "bad"
    done = [f"test ! -e {q(flag)}"]
    root, digest = target(tmp_path / "t", done)
    subprocess.run([GIT, "-C", str(root), "branch", "-q", "passing"], check=True)
    subprocess.run([GIT, "-C", str(root), "checkout", "-q", "-b", "old"], check=True)
    write(root / flag, "")
    subprocess.run([GIT, "-C", str(root), "add", flag], check=True)
    subprocess.run([GIT, "-C", str(root), *IDENTITY, "commit", "-qm", "old failure"], check=True)
    finish_check.measure(root, done, 600)
    tree = tmp_path / "wt"
    subprocess.run(
        [GIT, "-C", str(root), "worktree", "add", "-q", str(tree), "passing"], check=True
    )

    assert finish_check.known_record(tree, digest) is None
    write(tree / flag, "")
    assert hook("codex", digest, tree)[1]["decision"] == "block"
    write(root / "src.txt", "two\n")
    assert hook("codex", digest, root)[1]["systemMessage"].startswith("finish-check FAIL, known: ")


def test_two_targets_and_two_branches_keep_their_own_records(tmp_path: Path) -> None:
    """Breaks if measuring one target, or the same target on another branch, drops the record
    another one still applies, which would make it hold on every failure again."""

    done = ["exit 1"]
    root, digest = target(tmp_path / "t", done)
    inner = root / "inner"
    (inner / ".outcomebound").mkdir(parents=True)
    shutil.copy(root / ".outcomebound/manifest.json", inner / ".outcomebound/manifest.json")
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
    subprocess.run([GIT, "-C", str(root), *IDENTITY, "commit", "-qm", "inner"], check=True)
    finish_check.measure(root, done, 600)
    finish_check.measure(inner, done, 600)
    assert failing(root, digest) == failing(inner, digest) == {"exit 1": 1}

    tree = tmp_path / "wt"
    subprocess.run(
        [GIT, "-C", str(root), "worktree", "add", "-q", "-b", "side", str(tree)], check=True
    )
    write(tree / "side.txt", "")
    subprocess.run([GIT, "-C", str(tree), "add", "side.txt"], check=True)
    subprocess.run([GIT, "-C", str(tree), *IDENTITY, "commit", "-qm", "side"], check=True)
    write(root / "main.txt", "")
    subprocess.run([GIT, "-C", str(root), "add", "main.txt"], check=True)
    subprocess.run([GIT, "-C", str(root), *IDENTITY, "commit", "-qm", "main"], check=True)
    finish_check.measure(tree, done, 600)
    finish_check.measure(root, done, 600)
    assert failing(tree, digest) == failing(root, digest) == {"exit 1": 1}


def test_measure_runs_every_command_to_its_end_and_remembers_the_tree_it_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the install's one run stops at a failure, keeps a command the environment could
    not run as a known failure, or makes the first turn end on the tree it measured run Done
    again."""

    # A PATH with no entry the measurement leaves out, as a hook has, so a failure runs twice:
    # once, and once more in the same environment to tell a stable failure from a flake.
    environment, _ = finish_check.hook_environment(tmp_path, os.environ)
    monkeypatch.setenv("PATH", environment["PATH"])
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    count = tmp_path / "count"
    done = [f"echo run >> {q(count)}; exit 2", "true"]
    root, digest = target(tmp_path / "t", done)

    measured = finish_check.measure(root, done, 600)

    assert [r.verdict for r in measured.results] == ["FAIL", "PASS"]
    assert failing(root, digest) == {done[0]: 2}
    message = hook("codex", digest, root)[1]["systemMessage"]
    assert message.startswith("finish-check FAIL, known: ")
    assert "Not run again: the working tree is unchanged" in message
    assert len(count.read_text(encoding="utf-8").splitlines()) == 2

    other = ["no-such-tool-here", "exit 3"]
    root, digest = target(tmp_path / "u", other)
    measured = finish_check.measure(root, other, 600)
    assert [r.verdict for r in measured.results] == ["UNVERIFIED", "FAIL"]
    assert failing(root, digest) == {"exit 3": 3}
    assert hook("codex", digest, root)[1]["systemMessage"].startswith(
        "finish-check UNVERIFIED: `no-such-tool-here` could not run"
    )


def flaky(flag: Path, first: str, second: str) -> str:
    """A Done line that ends as `first` the first time it runs and as `second` after, a shell
    snippet each (`exit`, `echo` and `exit` or none), told apart by a flag file."""

    return f"if [ -e {q(flag)} ]; then {second}; fi; touch {q(flag)}; {first}"


@pytest.mark.parametrize(
    ("second", "ends"),
    [
        pytest.param("exit 0", "passed", id="passes"),
        pytest.param("echo 'FAILED tests/a.py::t'; exit 2", "failed with exit 2", id="exit"),
        pytest.param(
            "echo 'FAILED tests/a.py::two'; exit 1", "failed with other failure ids", id="ids"
        ),
    ],
)
def test_a_failure_that_does_not_repeat_is_a_possible_flake_and_kept_as_nothing(
    tmp_path: Path, second: str, ends: str
) -> None:
    """Breaks if a failure that a second run in the same environment does not repeat, with its
    exit code and failure ids, is kept as a known failure, which hides its next real failure, or
    if the tree a flake was measured on is remembered as checked."""

    first = "echo 'FAILED tests/a.py::one'; exit 1"
    done = [flaky(tmp_path / "flag", first, second)]
    root, digest = target(tmp_path / "t", done)

    measured = finish_check.measure(root, done, 600)

    (result,) = measured.results
    assert (result.verdict, result.cause) == (finish_check.UNVERIFIED, finish_check.FLAKE), result
    assert "possible flake" in result.why and ends in result.note
    assert measured.kept and failing(root, digest) == {}
    assert finish_check.last_checked(root) is None


def test_a_failure_that_repeats_is_known_and_runs_twice_where_no_path_entry_is_left_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a stable failure is not kept as known, or if it runs other than once and once
    more in the same environment."""

    environment, _ = finish_check.hook_environment(tmp_path, os.environ)
    monkeypatch.setenv("PATH", environment["PATH"])
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    count = tmp_path / "count"
    done = [f"echo run >> {q(count)}; echo 'FAILED tests/a.py::t'; exit 2"]
    root, digest = target(tmp_path / "t", done)

    measured = finish_check.measure(root, done, 600)

    assert measured.dropped == () and len(count.read_text(encoding="utf-8").splitlines()) == 2
    (result,) = measured.results
    assert result.verdict == finish_check.FAIL and result.known
    assert failing(root, digest) == {done[0]: 2}
    assert finish_check.last_checked(root) is not None


def test_the_measured_seconds_are_one_run_of_each_command_and_the_rerun_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the seconds kept and printed for a failing command count its rerun, which a
    hook never makes, so that a stable failure reads twice as slow as it runs."""

    environment, _ = finish_check.hook_environment(tmp_path, os.environ)
    monkeypatch.setenv("PATH", environment["PATH"])
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    # Only the rerun is slow, so the seconds tell one run from two on a runner of any speed: a
    # slow runner's shell start-up once made one quick run read as two.
    marker = tmp_path / "ran-once"
    done = [
        f"if [ -e {q(marker)} ]; then sleep 3; fi; touch {q(marker)}; "
        "echo 'FAILED tests/a.py::t'; exit 2"
    ]
    root, digest = target(tmp_path / "t", done)

    measured = finish_check.measure(root, done, 600)

    assert measured.reran == (done[0],)
    assert 0 < measured.seconds < 3, measured.seconds
    known = finish_check.known_record(root, digest)
    assert known is not None and known.seconds < 3


def test_a_dropped_path_entry_adds_one_run_to_a_stable_failure_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the run with the left-out PATH entries follows a flake, or does not follow a
    failure that repeated."""

    count = tmp_path / "count"
    root, _ = target(tmp_path / "t", ["true"])
    (root / "bin").mkdir()
    monkeypatch.setenv("PATH", os.pathsep.join([str(root / "bin"), *system_path()]))
    stable = [f"echo run >> {q(count)}; exit 2"]

    measured = finish_check.measure(root, stable, 600)

    assert measured.dropped == (str(root / "bin"),)
    assert len(count.read_text(encoding="utf-8").splitlines()) == 3
    count.unlink()
    done = [f"echo run >> {q(count)}; " + flaky(tmp_path / "flag", "exit 1", "exit 0")]
    measured = finish_check.measure(root, done, 600)
    assert [r.cause for r in measured.results] == [finish_check.FLAKE]
    assert len(count.read_text(encoding="utf-8").splitlines()) == 2


def test_a_known_failure_that_now_reads_as_a_flake_is_named_as_no_longer_known(
    tmp_path: Path,
) -> None:
    """Breaks if a measurement after which a known failure turns flaky replaces the record
    without saying that the failure is no longer known."""

    from outcomebound_tools import adopt

    always, flag = tmp_path / "always", tmp_path / "flag"
    fail = "echo 'FAILED tests/a.py::t'; exit 1"
    done = [f"if [ -e {q(always)} ]; then {fail}; fi; " + flaky(flag, fail, "exit 0")]
    write(always, "")
    root, digest = target(tmp_path / "t", done)
    first = finish_check.measure(root, done, 600)
    assert first.flaked == () and failing(root, digest) == {done[0]: 1}

    always.unlink()
    second = finish_check.measure(root, done, 600)

    assert second.previous is not None and second.flaked == (done[0],)
    assert failing(root, digest) == {}
    [known] = [n for n in adopt.measured_notes(root, second, 600) if n[0] == "known"]
    assert "new since the record measured on" in known[1]
    assert "is no longer known: it reads as a possible flake" in known[1]


def test_a_measurement_without_a_hook_uses_the_callers_path_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if `as_hook=False` still leaves out the callers's virtual environment, or the
    record it keeps does not say that the commands ran with the caller's PATH."""

    done = ["faketool"]
    root, digest = target(tmp_path / "t", done)
    venv = root / ".venv/bin"
    venv.mkdir(parents=True)
    write(venv / "faketool", "#!/bin/sh\nexit 0\n")
    other = tmp_path / "other/bin"
    other.mkdir(parents=True)
    write(other / "faketool", "#!/bin/sh\necho 'ERROR tests/x.py::t'\nexit 2\n")
    for tool in (venv / "faketool", other / "faketool"):
        tool.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(venv), str(other), *system_path()]))

    measured = finish_check.measure(root, done, 600, as_hook=False)

    (result,) = measured.results
    assert result.verdict == finish_check.PASS, result
    assert measured.dropped == () and measured.as_hook is False
    record = finish_check.known_record(root, digest)
    assert record is not None and record.as_hook is False and record.failing == {}


def test_commits_since_counts_the_commits_past_a_measured_one(tmp_path: Path) -> None:
    """Breaks if the count is not `rev-list --count`, or a commit Git lacks reads as zero."""

    root, _ = target(tmp_path / "t", ["true"])
    head = subprocess.run(
        [GIT, "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert finish_check.commits_since(root, head) == 0
    for number in (1, 2):
        write(root / "src.txt", f"{number}\n")
        subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
        subprocess.run([GIT, "-C", str(root), *IDENTITY, "commit", "-qm", "more"], check=True)
    assert finish_check.commits_since(root, head) == 2
    assert finish_check.commits_since(root, "0" * 40) is None
    empty = tmp_path / "empty"
    subprocess.run([GIT, "init", "-q", str(empty)], check=True)
    assert finish_check.commits_since(empty, "") == 0
    assert finish_check.commits_since(root, "") is None


def test_a_known_record_is_read_only_in_its_own_shape() -> None:
    """Breaks if a damaged record of known failures is trusted, which could hide a failure, or
    if a failure kept as a bare exit code is not read as naming no failure ids."""

    failure = finish_check.Failure(2, frozenset({"pytest a.py::t"}))
    good = finish_check.Known("a" * 64, "", "b" * 40, "2026-10-04", 1.0, {"make test": failure})
    document = good.document()
    assert finish_check.parse_known(json.dumps({"records": [document]})) == [good]
    bare = {**document, "failing": {"make test": 2}}
    read = finish_check.parse_known(json.dumps({"records": [bare]}))
    assert read is not None and read[0].failing == {"make test": finish_check.Failure(2)}
    for text in (
        "",
        "not json",
        json.dumps(document),
        json.dumps({"records": [{**document, "failing": {"make test": "2"}}]}),
        json.dumps({"records": [{**document, "done": "short"}]}),
        json.dumps({"records": [{**document, "head": "main"}]}),
        json.dumps({"records": [{k: v for k, v in document.items() if k != "head"}]}),
    ):
        assert finish_check.parse_known(text) is None


# --- What `run_one` reads at exit 126 and 127, and where the line runs ---------------------


def _verdict(tmp_path: Path, line: str) -> finish_check.Result:
    return finish_check.run_one(tmp_path, line, 60)


def test_something_that_ran_before_a_missing_last_tool_is_a_failure_at_exit_127(
    tmp_path: Path,
) -> None:
    """Breaks if the exit-127 branch skips the rule that the not-found line be the command's
    only word: a Python traceback, and then a tool that is not there, read UNVERIFIED and held
    nothing, though the first command had failed and the missing last tool shows nothing about
    it."""

    python = q(sys.executable)
    failed = _verdict(tmp_path, f"{python} -c 'raise AssertionError(1)'; nosuchtool-zz")
    assert (failed.verdict, failed.code) == (finish_check.FAIL, 127), failed.output

    loud = _verdict(tmp_path, "echo built; nosuchtool-zz")
    assert (loud.verdict, loud.code) == (finish_check.FAIL, 127), loud.output


def test_a_missing_tool_that_is_the_commands_only_word_is_unverified_at_exit_127(
    tmp_path: Path,
) -> None:
    """Breaks if the rule above also fails a command whose only output is the shell's own word
    that its tool is not there, or an echo of that tool first: the hook's PATH, not the work,
    is what lacks it."""

    alone = _verdict(tmp_path, "nosuchtool-zz --check")
    assert (alone.verdict, alone.cause, alone.code) == (
        finish_check.UNVERIFIED,
        finish_check.ENVIRONMENT,
        127,
    ), alone.output
    echoed = _verdict(tmp_path, "echo nosuchtool-zz; nosuchtool-zz")
    assert echoed.verdict == finish_check.UNVERIFIED, echoed.output


@pytest.mark.parametrize(
    ("output", "ran"),
    [
        (b"sh: 1: nosuchtool-zz: not found\n", False),
        (b"sh: nosuchtool-zz: not found\n", False),
        (b"sh: line 1: nosuchtool-zz: command not found\n", False),
        (
            b"Traceback (most recent call last):\nAssertionError: 1\n"
            b"sh: 1: nosuchtool-zz: not found\n",
            True,
        ),
        (b"built\nsh: nosuchtool-zz: not found\n", True),
        (b"built\nsh: 1: ./not-executable: Permission denied\n", True),
    ],
)
def test_a_not_found_line_is_told_in_each_shells_words_and_what_ran_before_it(
    output: bytes, ran: bool
) -> None:
    """Breaks if the dash, bash or busybox form of the shell's word is not read (busybox says
    `sh: tool: not found`, with no line number and no `command`), so that an Alpine hook cannot
    tell a command that ran before its missing tool, or if a line in no listed form is read as
    one."""

    assert finish_check.ran_before_missing(output) is ran
    named = finish_check.missing_tool(output)
    assert (named is None) is (ran or b"Permission" in output)
    assert named in (None, "nosuchtool-zz")


@pytest.mark.parametrize("available", [False, True])
def test_a_done_command_uses_the_shell_of_the_environment_it_runs_with(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, available: bool
) -> None:
    """Breaks if a supplied Windows PATH lacks a shell but the caller's shell runs anyway,
    or if a shell supplied only by that PATH is ignored."""

    shell = programs.posix_shell()
    assert shell is not None
    marker = tmp_path / "ran"

    def choose(environment: dict[str, str] | None = None) -> str | None:
        present = available if environment is not None else not available
        return shell if present else None

    monkeypatch.setattr(finish_check.programs, "posix_shell", choose)

    result = finish_check.run_one(tmp_path, f"echo ran > {q(marker)}", 60, {"PATH": ""})

    expected = finish_check.PASS if available else finish_check.UNVERIFIED
    assert result.verdict == expected, result
    assert marker.exists() is available
    if not available:
        assert "no POSIX shell" in result.why


def test_no_posix_shell_reads_unverified_with_the_reason_and_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a Windows machine with no Git for Windows holds the turn, or names no reason,
    or starts something else: the Done line needs a POSIX shell, and without one the check
    cannot say anything about it."""

    marker = tmp_path / "ran"
    monkeypatch.setattr(finish_check.programs, "posix_shell", lambda *a, **k: None)

    result = finish_check.run_one(tmp_path, f"touch {marker}", 60)

    assert (result.verdict, result.cause, result.seconds) == (
        finish_check.UNVERIFIED,
        finish_check.ENVIRONMENT,
        0.0,
    )
    assert "no POSIX shell" in result.why and "Git for Windows" in result.why
    assert not marker.exists()


def test_a_signal_that_ends_the_check_never_kills_it_through_os_kill_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a held stop on Windows is sent to the process with `os.kill`, which ends it
    there at once with the signal's number as its exit code and no `finally`: Ctrl-C is the
    exception Python raises, and another signal exits as a shell reports it, 128 plus its
    number, so each running command's tree is stopped first."""

    def refused(*_: Any) -> None:
        raise AssertionError("os.kill sends a signal on Windows that ends the process")

    monkeypatch.setattr(finish_check.os, "kill", refused)
    with pytest.raises(KeyboardInterrupt):
        finish_check._die(signal.SIGINT, windows=True)
    with pytest.raises(SystemExit) as stopped:
        finish_check._die(signal.SIGTERM, windows=True)
    assert stopped.value.code == 128 + signal.SIGTERM


@pytest.mark.parametrize(
    ("given", "native"),
    [
        ("/c/work/app/work", "C:/work/app/work"),
        ("/d", "D:/"),
        ("/cygdrive/e/src", "E:/src"),
        ("/srv/app", "/srv/app"),
        ("/opt/app", "/opt/app"),
        ("C:/work/app", "C:/work/app"),
        ("sub/dir", "sub/dir"),
    ],
)
def test_a_folder_written_the_way_git_bash_writes_it_is_read_as_a_drive_on_windows(
    given: str, native: str
) -> None:
    """Breaks if a hook input's `cwd` of `/c/work/app` is read, on Windows, as a folder named
    `c` on the current drive: no manifest is found there, and the finish check holds nothing
    with a report that names the wrong folder."""

    assert finish_check.native_path(given, windows=True) == native


def test_a_folder_in_git_bash_form_is_left_alone_off_windows() -> None:
    """Breaks if a POSIX folder whose first name is one letter, `/a/work`, is rewritten as a
    drive: it is a real folder there."""

    assert finish_check.native_path("/c/work/app", windows=False) == "/c/work/app"


def test_a_command_the_report_prints_for_a_person_names_the_target_as_the_platform_quotes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a printed `outcomebound adopt <folder>` quotes the folder for POSIX alone, so
    that a person on Windows pastes a word PowerShell and Git Bash read differently: on Windows
    a single quote inside a quoted word is doubled, which POSIX quoting does not do. Windows is
    emulated here, as `paths.on_windows` says it; no Windows run has shown the pasted text."""

    monkeypatch.setattr(finish_check.paths, "on_windows", lambda: True)
    folder = Path("/work/it's here")
    results = [finish_check.Result("slow", finish_check.UNVERIFIED, 5.0, "stopped", cause="time")]

    message = finish_check.verdict_for(results, False, folder, 60)["systemMessage"]

    assert "outcomebound adopt '/work/it''s here' --finish-timeout" in message
    assert "outcomebound adopt '/work/it''s here' --no-finish-check" in message


# --- The tree a turn began with ---------------------------------------------------


def turn(row: str, digest: str, root: Path) -> None:
    """The prompt that begins a turn: the mark runs, prints nothing and succeeds."""

    done = mark(row, digest, root)
    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")


def counted(count: Path) -> int:
    return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0


@pytest.mark.parametrize("row", ROWS)
def test_a_turn_that_changed_nothing_runs_nothing_and_holds_nothing_on_a_failing_tree(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a turn that edited no file and made no commit is held, or runs Done, for a
    failure that was there when it began (a stale package outside the tree); the mark is kept in
    the Git directory, never in the working tree."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])

    turn(row, digest, root)
    verdict = hook(row, digest, root)[1]

    assert list(verdict) == ["systemMessage"] and counted(count) == 0
    assert verdict["systemMessage"].startswith(
        "finish-check: the tree is the one this turn began with (marked "
    )
    assert verdict["systemMessage"].endswith("); Done was not run.")
    assert not (root / ".git" / finish_check.MARK).exists()  # the stop ended the turn
    status = subprocess.run(
        [GIT, "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    assert finish_check.MARK not in status.stdout


def test_an_unchanged_turn_repeats_a_recorded_non_pass_for_the_person_and_runs_nothing(
    tmp_path: Path,
) -> None:
    """Breaks if an unchanged turn on a tree whose last verdict is a failure loses that verdict
    or holds again, or runs Done."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])
    assert hook("codex", digest, root)[1]["decision"] == "block" and counted(count) == 1

    turn("codex", digest, root)
    verdict = hook("codex", digest, root)[1]

    assert list(verdict) == ["systemMessage"] and counted(count) == 1
    assert "so it was not run again" in verdict["systemMessage"]
    assert "(marked " in verdict["systemMessage"]


def suite(tmp_path: Path) -> tuple[Path, str, Path]:
    """A target whose Done fails for each flag file in a folder outside the tree, as a test
    suite fails for a stale package: the failures are the environment's, not the tree's."""

    flags = tmp_path / "flags"
    flags.mkdir()
    root, _ = target(tmp_path / "t", ["true"])
    line = runner_script(root, flags)
    manifest = json.loads((root / finish_check.MANIFEST).read_text(encoding="utf-8"))
    manifest["artifacts"][0]["done"] = [line]
    write(root / finish_check.MANIFEST, json.dumps(manifest))
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
    subprocess.run([GIT, "-C", str(root), *IDENTITY, "commit", "-qm", "done"], check=True)
    return root, finish_check.done_digest([line]), flags


@pytest.mark.parametrize("row", ROWS)
def test_a_changed_turn_with_the_failure_it_began_with_reports_it_and_holds_nothing(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a failure the tree had when the turn began, with the same failure ids, holds
    the turn once the turn has edited a file, or is not named as known before the turn."""

    root, digest, flags = suite(tmp_path)
    write(flags / "old", "")
    assert hook(row, digest, root)[1]["decision"] == "block"
    turn(row, digest, root)
    write(root / "src.txt", "two\n")

    verdict = hook(row, digest, root)[1]

    assert list(verdict) == ["systemMessage"]
    message = verdict["systemMessage"]
    assert message.startswith("finish-check FAIL, known before this turn: ")
    began = "as on the working tree this turn began with"
    assert f"{began} (known by its failure ids; known before this turn, not held)" in message


@pytest.mark.parametrize("row", ROWS)
def test_a_changed_turn_with_a_new_failure_holds(tmp_path: Path, row: str) -> None:
    """Breaks if a failure the tree did not have when the turn began is let through because the
    turn began on a failing tree, whether the new failure is inside a command that already
    failed or in another command."""

    root, digest, flags = suite(tmp_path)
    write(flags / "old", "")
    assert hook(row, digest, root)[1]["decision"] == "block"
    turn(row, digest, root)
    write(root / "src.txt", "two\n")
    write(flags / "new", "")

    verdict = hook(row, digest, root)[1]

    assert verdict["decision"] == "block"
    assert "tests/new.py::test_x" in verdict["reason"]


def test_a_commit_the_turn_made_counts_as_a_change(tmp_path: Path) -> None:
    """Breaks if the turn's start is compared with HEAD alone or the tree alone: an empty commit
    leaves the tree digest as it was and changes HEAD, and the turn ran after it."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])
    turn("codex", digest, root)
    subprocess.run(
        [GIT, "-C", str(root), *IDENTITY, "commit", "-q", "--allow-empty", "-m", "more"],
        check=True,
    )

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and counted(count) == 1


@pytest.mark.parametrize("row", ROWS)
def test_with_no_mark_a_failure_holds_as_before(tmp_path: Path, row: str) -> None:
    """Breaks if an install or harness that writes no turn mark behaves any other way: a failing
    tree held, however the turn began; also a mark from another tree is not a baseline."""

    root, digest, flags = suite(tmp_path)
    write(flags / "old", "")
    assert hook(row, digest, root)[1]["decision"] == "block"
    write(root / "src.txt", "two\n")
    assert hook(row, digest, root)[1]["decision"] == "block"

    other, other_digest = target(tmp_path / "other", ["exit 1"])
    turn(row, other_digest, other)
    (other / ".git" / finish_check.MARK).replace(root / ".git" / finish_check.MARK)
    write(root / "src.txt", "three\n")
    assert hook(row, digest, root)[1]["decision"] == "block"


def test_an_unreadable_mark_is_no_mark(tmp_path: Path) -> None:
    """Breaks if a mark the verb cannot read, or one that names the head and tree of another
    state, stops the check from running: the check then behaves as with no mark."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; exit 1"])
    for text in ("not json", '{"head": 1, "tree": 2}', ""):
        write(root / ".git" / finish_check.MARK, text)
        write(root / "src.txt", text + "\n")
        assert hook("codex", digest, root)[1]["decision"] == "block"


@pytest.mark.parametrize("case", ["no-manifest", "not-a-digest", "unknown-row", "no-repository"])
def test_the_mark_never_fails_the_prompt_and_writes_nothing_on_an_error(
    tmp_path: Path, case: str
) -> None:
    """Breaks if an error in the mark prints to the model, exits non-zero (a prompt then shows a
    hook error) or leaves a mark."""

    root, digest = target(tmp_path / "t", ["true"])
    where, row, given = tmp_path / "w", "codex", digest
    where.mkdir()
    if case == "no-repository":
        (where / ".outcomebound").mkdir()
        write(where / finish_check.MANIFEST, "{}")
    elif case == "not-a-digest":
        where, given = root, "abc"
    elif case == "unknown-row":
        where, row = root, "nonesuch"

    done = mark(row, given, where)

    assert (done.returncode, done.stdout) == (0, b"")
    assert not list(tmp_path.glob(f"**/{finish_check.MARK}*"))


def test_a_mark_that_cannot_be_renewed_is_removed(tmp_path: Path) -> None:
    """Breaks if a prompt of another session whose tree cannot be read leaves the mark of an
    earlier prompt, which would stand for a tree this turn did not begin with."""

    root, digest = target(tmp_path / "t", ["true"])
    turn("codex", digest, root)
    old = root / ".git" / finish_check.MARK
    assert old.is_file()
    write(root / ".git" / "index", "not an index")
    next_session = {"session_id": "next", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}

    done = mark("codex", digest, root, stdin=next_session)

    assert (done.returncode, done.stdout) == (0, b"") and not old.exists()


# --- A mark only the prompt hook can write, and only before the turn's first work ---


def mark_time(root: Path) -> datetime:
    document = json.loads((root / ".git" / finish_check.MARK).read_text(encoding="utf-8"))
    when = finish_check.stamp(document["time"])
    assert when is not None and document["session"] == "s"
    return when


@pytest.mark.parametrize(
    "stdin",
    [
        {"session_id": "s", "hook_event_name": "Stop"},
        {"session_id": "s"},
        {"hook_event_name": "UserPromptSubmit"},
        {"session_id": "", "hook_event_name": "UserPromptSubmit"},
        b"",
        b"[]",
    ],
    ids=["stop-input", "no-event", "no-session", "empty-session", "no-input", "not-an-object"],
)
def test_the_mark_is_written_only_on_a_prompt_hooks_input(tmp_path: Path, stdin: Any) -> None:
    """Breaks if the agent can write a mark by running the verb itself, whatever it feeds it:
    the event the row documents and a session id are the harness's input, and nothing else
    writes."""

    root, digest = target(tmp_path / "t", ["true"])
    if isinstance(stdin, dict):
        stdin = {**stdin, "cwd": str(root)}

    done = mark("codex", digest, root, stdin=stdin)

    assert (done.returncode, done.stdout) == (0, b"")
    assert not (root / ".git" / finish_check.MARK).exists()


@pytest.mark.parametrize("row", ROWS)
def test_the_mark_keeps_its_session_and_time(tmp_path: Path, row: str) -> None:
    """Breaks if the mark does not say which session wrote it and when, which the stop and the
    person's message read."""

    root, digest = target(tmp_path / "t", ["true"])
    before = datetime.now(timezone.utc)

    turn(row, digest, root)

    assert before <= mark_time(root) <= datetime.now(timezone.utc)


@pytest.mark.parametrize("row", ROWS)
def test_another_sessions_mark_is_not_used(tmp_path: Path, row: str) -> None:
    """Breaks if a mark written for one session lets another session's turn end unchecked: the
    stop reads the mark only for its own session id."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    other = {"session_id": "another", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}
    assert mark(row, digest, root, stdin=other).returncode == 0

    assert hook(row, digest, root)[1]["decision"] == "block"


@pytest.mark.parametrize("row", ROWS)
def test_a_mark_written_after_the_turns_first_work_is_not_used(tmp_path: Path, row: str) -> None:
    """Breaks if an agent that runs the verb with a forged prompt input after its edits, which
    its own tool calls already show in the transcript, makes its turn read as unchanged."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    turn(row, digest, root)

    assert hook(row, digest, root, transcript="past")[1]["decision"] == "block"


@pytest.mark.parametrize("row", ROWS)
@pytest.mark.parametrize("transcript", ["garbage", "missing"])
def test_a_transcript_that_cannot_be_read_means_no_mark(
    tmp_path: Path, row: str, transcript: str
) -> None:
    """Breaks if a stop whose transcript is unreadable or not parsed trusts the mark: it runs
    and holds as without one."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    turn(row, digest, root)

    assert hook(row, digest, root, transcript=transcript)[1]["decision"] == "block"


@pytest.mark.parametrize("row", ROWS)
def test_a_stop_input_without_a_transcript_gets_the_session_check_alone(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a row whose stop input names no transcript loses the mark altogether, which
    the design names as that row's limit, or if the session check is skipped there."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    turn(row, digest, root)

    assert "Done was not run" in hook(row, digest, root, transcript="none")[1]["systemMessage"]
    wrong = {**INPUT[row], "cwd": str(root), "session_id": "elsewhere", "transcript_path": None}
    assert hook(row, digest, root, stdin=wrong)[1]["decision"] == "block"


@pytest.mark.parametrize("row", ROWS)
def test_each_use_of_the_mark_is_told_to_the_person_with_its_time(tmp_path: Path, row: str) -> None:
    """Breaks if a stop that is not run, or not held, because of the mark says nothing, or does
    not name when the mark was written, so that the person sees every use."""

    root, digest, flags = suite(tmp_path)
    write(flags / "old", "")
    assert hook(row, digest, root)[1]["decision"] == "block"
    turn(row, digest, root)
    clock = mark_time(root).astimezone().strftime("%H:%M:%S")

    unchanged = hook(row, digest, root)[1]["systemMessage"]
    assert f"(marked {clock})" in unchanged and "not run again" in unchanged

    turn(row, digest, root)
    clock = mark_time(root).astimezone().strftime("%H:%M:%S")
    write(root / "src.txt", "two\n")
    known = hook(row, digest, root)[1]["systemMessage"]
    assert f"(marked {clock})" in known and known.startswith("finish-check FAIL, known before")


@pytest.mark.parametrize("row", ROWS)
def test_an_unchanged_turn_is_told_once_for_a_session_and_tree(tmp_path: Path, row: str) -> None:
    """Breaks if a session that only reads is told "Done was not run" after every reply, or if a
    changed tree or another session is not told again."""

    root, digest = target(tmp_path / "t", ["true"])

    turn(row, digest, root)
    assert "Done was not run" in hook(row, digest, root)[1]["systemMessage"]
    turn(row, digest, root)
    assert hook(row, digest, root)[1] == {}

    write(root / "src.txt", "two\n")
    turn(row, digest, root)
    assert "Done was not run" in hook(row, digest, root)[1]["systemMessage"]
    turn(row, digest, root)
    assert hook(row, digest, root)[1] == {}

    other = {"session_id": "another", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}
    assert mark(row, digest, root, stdin=other).returncode == 0
    stop = {**INPUT[row], "cwd": str(root), "session_id": "another", "transcript_path": None}
    assert "Done was not run" in hook(row, digest, root, stdin=stop)[1]["systemMessage"]


# --- A turn keeps the mark of its first prompt ---------------------------------------


def stop_input(row: str, root: Path, **fields: Any) -> dict[str, Any]:
    """A stop input of `row` with no transcript, so that only the session check applies."""

    return {**INPUT[row], "cwd": str(root), "transcript_path": None, **fields}


@pytest.mark.parametrize("row", ROWS)
def test_a_prompt_event_inside_a_turn_does_not_move_the_baseline(tmp_path: Path, row: str) -> None:
    """Breaks if a second prompt event of the same session (a queued message the harness
    delivers mid-turn) rewrites the mark after the turn's edits, so that the stop reads the
    changed tree as the one the turn began with and runs nothing."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])
    turn(row, digest, root)
    write(root / "src.txt", "two\n")
    turn(row, digest, root)

    verdict = hook(row, digest, root)[1]

    assert "PASS" in verdict["systemMessage"] and counted(count) == 1


@pytest.mark.parametrize("row", ROWS)
def test_the_stop_ends_the_mark_unless_it_holds_or_the_session_is_paused(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a mark outlives the turn it began, which a later turn that reverts to that
    tree would read as unchanged; or if a hold ends it, so that a harness that fires the prompt
    event for the retry (codex) moves the baseline past the edits; or if the retry stop does not
    end it, so that the next prompt cannot write a new one."""

    root, digest, flags = suite(tmp_path)
    write(flags / "old", "")
    assert hook(row, digest, root)[1]["decision"] == "block"
    mark_file = root / ".git" / finish_check.MARK
    turn(row, digest, root)
    write(root / "src.txt", "two\n")
    write(flags / "new", "")

    assert hook(row, digest, root)[1]["decision"] == "block" and mark_file.is_file()
    turn(row, digest, root)  # the prompt a hold creates (codex): the baseline stays
    retry = stop_input(row, root, stop_hook_active=True)
    assert list(hook(row, digest, root, stdin=retry)[1]) == ["systemMessage"]
    assert not mark_file.exists()

    turn(row, digest, root)
    assert mark_file.is_file()
    unchanged = hook(row, digest, root)[1]["systemMessage"]
    assert "(marked " in unchanged and "not run again" in unchanged
    assert not mark_file.exists()


def test_a_paused_claude_code_session_keeps_the_mark(tmp_path: Path) -> None:
    """Breaks if a stop that only pauses the session (background work in flight) ends the
    turn's mark."""

    root, digest = target(tmp_path / "t", ["true"])
    turn("claude-code", digest, root)
    paused = stop_input("claude-code", root, background_tasks=[{"id": "b"}])

    assert hook("claude-code", digest, root, stdin=paused)[1] == {}
    assert (root / ".git" / finish_check.MARK).is_file()


@pytest.mark.parametrize(
    "extra",
    [
        {"isCompactSummary": True, "message": {"role": "user", "content": "x"}},
        {
            "origin": {"kind": "task-notification"},
            "promptSource": "system",
            "message": {"role": "user", "content": "<task-notification>x"},
        },
        {"message": {"role": "user", "content": "<command-name>/x</command-name>"}},
        {"message": {"role": "user", "content": "<local-command-stdout>x"}},
        {
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "[Request interrupted"}],
            }
        },
    ],
    ids=["compaction", "task-notification", "slash-command", "command-output", "interrupt"],
)
def test_a_line_the_harness_writes_is_not_a_prompt_for_the_order_check(
    tmp_path: Path, extra: dict[str, Any]
) -> None:
    """Breaks if a user-typed line the harness writes itself (a compaction summary, a task
    notification, a slash-command echo, an interrupt) ends the turn's window: the mark written
    after the first work would then be trusted. A real person's prompt does, as a control."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    turn("claude-code", digest, root)
    now = datetime.now(timezone.utc)

    def lines(between: dict[str, Any]) -> Path:
        rows = [
            {
                "type": "user",
                "timestamp": (now - timedelta(hours=3)).isoformat(),
                "message": {"role": "user", "content": "hi"},
            },
            {"type": "assistant", "timestamp": (now - timedelta(hours=2)).isoformat()},
            {"type": "user", "timestamp": (now - timedelta(hours=1)).isoformat(), **between},
            {"type": "assistant", "timestamp": (now + timedelta(hours=1)).isoformat()},
        ]
        path = tmp_path / "transcript.jsonl"
        write(path, "".join(json.dumps(row) + "\n" for row in rows))
        return path

    human = {"origin": {"kind": "human"}, "message": {"role": "user", "content": "again"}}
    control = stop_input("claude-code", root, transcript_path=str(lines(human)))
    assert (
        "Done was not run" in hook("claude-code", digest, root, stdin=control)[1]["systemMessage"]
    )

    turn("claude-code", digest, root)
    forged = stop_input("claude-code", root, transcript_path=str(lines(extra)))
    assert hook("claude-code", digest, root, stdin=forged)[1]["decision"] == "block"


def test_absence_confirmation_uses_the_effective_child_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool added by the shell adapter cannot excuse its own failed check by
    printing a missing-tool line. Its actual child PATH proves it is present."""
    folder = tmp_path / "shell-tools"
    folder.mkdir()
    tool = folder / "present-tool"
    write(tool, "#!/bin/sh\nprintf '%s\\n' 'sh: present-tool: command not found'\nexit 2\n")
    tool.chmod(0o755)
    root, _ = target(tmp_path / "project", ["present-tool"])
    compose = programs.shell_environment

    def with_tool(shell: str, environment: Any = None) -> dict[str, str]:
        effective = dict(compose(shell, environment) or os.environ)
        effective["PATH"] = str(folder) + os.pathsep + effective.get("PATH", "")
        return effective

    monkeypatch.setattr(programs, "shell_environment", with_tool)
    environment = dict(os.environ, PATH=os.pathsep.join(system_path()))
    result = finish_check.run_one(root, "present-tool", 60, environment)
    assert (result.verdict, result.code) == (finish_check.FAIL, 2), result
    assert finish_check.verdict_for([result], True, root, 60).get("decision") == "block"


@posix_only
def test_an_unset_path_cannot_disprove_the_shell_default_path(tmp_path: Path) -> None:
    line = "command -v cat >/dev/null && printf 'sh: cat: command not found\\n'; exit 2"
    result = finish_check.run_one(tmp_path, line, 5, {})
    assert (result.verdict, result.code) == (finish_check.FAIL, 2), result


@posix_only
def test_an_absolute_module_probe_does_not_require_path(tmp_path: Path) -> None:
    result = finish_check.run_one(tmp_path, f"{q(sys.executable)} -m no_such_module_here", 5, {})
    assert result.verdict == finish_check.UNVERIFIED, result


@pytest.mark.parametrize(
    "line",
    [
        "./removed-check.sh",
        "sh scripts/removed-check.sh",
        "'./removed check.sh'",
        "sh 'scripts/removed check.sh'",
        "'./removed:check.sh'",
        "'./missing\nhelper.sh'",
    ],
)
def test_a_missing_project_helper_fails_and_holds(tmp_path, line):
    root, digest = target(tmp_path / "t", [line])
    result = finish_check.run_one(root, line, 60)
    assert result.verdict == finish_check.FAIL
    _, verdict = hook("codex", digest, root)
    assert verdict["decision"] == "block"
    assert "FAIL" in verdict["reason"]


@pytest.mark.parametrize("code", [126, 127])
def test_exit_code_without_environment_evidence_is_a_failure(tmp_path: Path, code: int) -> None:
    root, digest = target(tmp_path / "t", [f"exit {code}"])
    verdict = hook("codex", digest, root)[1]
    assert verdict["decision"] == "block"
    assert f"exit {code}" in verdict["reason"]


@pytest.mark.parametrize("nested", [False, True])
def test_known_records_resolve_git_common_dir_without_path_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nested: bool
) -> None:
    root, digest = target(tmp_path / "project with spaces", ["exit 1"])
    where = root / "component" if nested else root
    where.mkdir(exist_ok=True)
    original_git = finish_check._git

    def older_git(target_path, *arguments, **options):
        if any(arg.startswith("--path-format") for arg in arguments):
            return None
        return original_git(target_path, *arguments, **options)

    monkeypatch.setattr(finish_check, "_git", older_git)
    record = finish_check.Known(
        digest, "component/" if nested else "", "", "2026-10-08T00:00:00+00:00", 0.0, {}
    )
    assert finish_check.keep_known(where, record)
    saved = root / ".git" / finish_check.KNOWN
    assert saved.is_file()
    assert finish_check.parse_known(saved.read_text(encoding="utf-8")) == [record]
