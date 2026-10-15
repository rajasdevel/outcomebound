"""`outcomebound finish-check`, the verb a harness's stop hook runs.

Each test runs the launcher in a real subprocess on a scratch Git repository under `tmp_path`,
with the hook's input on stdin in the row's own shape, and reads the JSON the harness would read.
Each names the break it catches.
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import adapters, finish_check, programs
from tests import finish_helpers
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


def stop_input_for(row: str, root: Path, working: Path, transcript: str) -> dict[str, Any]:
    """The stop input `row` sends, the guard unset, with a transcript in the row's shape."""

    stdin = {**INPUT[row], "cwd": str(working)}
    path = root.parent / f"transcript-{row}.jsonl"
    if transcript in ("future", "past"):
        write_transcript(path, row, transcript)
    elif transcript == "garbage":
        write(path, "not json\n")
    stdin["transcript_path"] = str(path) if transcript != "none" else None
    return stdin


def fire(
    row: str,
    digest: str,
    root: Path,
    stdin: bytes | dict[str, Any] | None = None,
    cwd: Path | None = None,
    timeout: int | None = None,
    transcript: str = "future",
    background: bool = False,
) -> Any:
    """Run the stop entry once as `row` fires it, the input's `cwd` naming where the agent works
    unless `stdin` is given. claude-code runs from the checkout its session started in, which its
    root variable still names, while the agent works in `root`, as after it moves into a
    worktree; codex runs from a directory below `root`, the session's `cwd`. With `background`,
    the process is returned running, its input written and closed."""

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
        stdin = stop_input_for(row, root, working, transcript)
    data = stdin if isinstance(stdin, bytes) else json.dumps(stdin).encode()
    words = engine("finish-check", "--constant-time", "--harness", row, "--done", digest)
    if timeout is not None:
        words += ["--timeout", str(timeout)]
    if background:
        process = subprocess.Popen(
            words,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=environment,
        )
        assert process.stdin is not None
        process.stdin.write(data)
        process.stdin.close()
        process.stdin = None  # written and closed: `communicate` has nothing more to send
        return process
    return subprocess.run(
        words,
        input=data,
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
        timeout=180,
    )


def hook(
    row: str,
    digest: str,
    root: Path,
    stdin: bytes | dict[str, Any] | None = None,
    cwd: Path | None = None,
    timeout: int | None = None,
    transcript: str = "future",
    run: bool = True,
) -> tuple[int, dict[str, Any]]:
    """A turn end as `row` delivers it, in codex's words: `{"decision": "block", "reason": ...}`
    for a hold, a `systemMessage` for the person, `{}` for nothing.

    claude-code's entry is the run itself: it exits 2 with the report on standard error where it
    holds, and otherwise exits 0 and prints nothing on either stream, which this asserts; the
    person reads the rest through the turn-start entry or `--status` (`person`).

    codex's stop prints its JSON and starts the run in the background. Where `run`, a run must
    start; once it has ended, the next stop, with the same input, delivers what it found, and that
    stop's JSON is returned, unless the first stop held. Without `run`, the first stop's JSON is
    returned as it is: the turn changed nothing, or the tree has a record."""

    if row == "claude-code":
        done = fire(row, digest, root, stdin, cwd, timeout, transcript)
        assert isinstance(done, subprocess.CompletedProcess)
        if done.returncode == 2:
            assert done.stdout == b"", done.stdout
            return 2, {"decision": "block", "reason": done.stderr.decode("utf-8")}
        assert (done.returncode, done.stdout, done.stderr) == (0, b"", b""), done
        return 0, {}
    working = cwd or root / "deeper"
    if stdin is None:
        working.mkdir(exist_ok=True)
        stdin = stop_input_for(row, root, working, transcript)
    since = finish_helpers.now()
    done = fire(row, digest, root, stdin, cwd, timeout, transcript)
    assert isinstance(done, subprocess.CompletedProcess)
    assert done.returncode == 0, done.stderr.decode()
    first: dict[str, Any] = json.loads(done.stdout)
    if not run:
        return done.returncode, first
    finish_helpers.wait_for_run(git_root(root), since)
    if "decision" in first:
        return done.returncode, first
    since = finish_helpers.now()
    again = fire(row, digest, root, stdin, cwd, timeout, transcript)
    assert isinstance(again, subprocess.CompletedProcess)
    assert again.returncode == 0, again.stderr.decode()
    # The delivering stop may start a run of its own (a record that never repeats, such as a
    # missing tool's): it ends before the next turn end of the test.
    finish_helpers.settle(git_root(root), since)
    result: dict[str, Any] = json.loads(again.stdout)
    return again.returncode, result


def git_root(root: Path) -> Path:
    """The checkout `root` is in: itself, or the repository above a target in a subfolder; a
    worktree's `.git` is a file, which counts."""

    for folder in (root, *root.parents):
        if (folder / ".git").exists():
            return folder
    return root


def person(row: str, root: Path, verdict: dict[str, Any]) -> str:
    """What the person reads after a turn end that did not hold: codex's `systemMessage`, and on
    claude-code, whose entry prints nothing, `--status`."""

    if row == "codex":
        assert list(verdict) == ["systemMessage"], verdict
        return str(verdict["systemMessage"])
    assert verdict == {}, verdict
    return finish_helpers.status(git_root(root))


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

    message = person(row, root, verdict)
    if row == "codex":
        assert message.startswith("finish-check PASS: true, echo ok, ")
        assert message.endswith("; not reviewed, not landed")
    else:
        assert "finish-check PASS: true, echo ok, " in message
        assert "; not reviewed, not landed" in message


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

    _, verdict = hook(row, written_for, root, run=False)

    if row == "codex":
        assert list(verdict) == ["systemMessage"]
        message = verdict["systemMessage"]
    else:
        # The entry prints nothing; the turn-start entry, which carries the same digest, says it.
        assert verdict == {}
        message = turn(row, written_for, root)
    assert message.startswith("finish-check UNVERIFIED: ")
    assert "outcomebound adopt" in message
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

    # claude-code: the entry prints nothing and exits 0, and `--status` shows the report.
    other, other_digest = target(tmp_path / "c", ["echo boom; exit 1"])
    given = {**stdin, "cwd": str(other)} if isinstance(stdin, dict) else stdin
    _, quiet = hook("claude-code", other_digest, other, stdin=given, cwd=other)
    shown = person("claude-code", other, quiet)
    assert "finish-check FAIL: " in shown and "```output\nboom\n```" in shown


WAITING = [{"background_tasks": [{"task_id": "b1"}]}, {"session_crons": [{"id": "c1"}]}]


def paused(root: Path, waiting: dict[str, Any]) -> dict[str, Any]:
    return {**INPUT["claude-code"], "cwd": str(root), **waiting}


@pytest.mark.parametrize("waiting", WAITING, ids=["background-tasks", "session-crons"])
def test_a_paused_session_runs_done_and_holds_nothing_until_a_stop_that_is_not_paused(
    tmp_path: Path, waiting: dict[str, Any]
) -> None:
    """Breaks if a paused session skips Done (one session skipped it at 344 stops in a row), if
    a failure found while it is paused holds the paused stop, or if that failure is lost: the
    first stop that is not paused, on the same tree, holds it without running Done again."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])

    assert hook("claude-code", digest, root, stdin=paused(root, waiting)) == (0, {})
    assert counted(count) == 1
    assert "finish-check FAIL" in finish_helpers.status(root)

    code, verdict = hook("claude-code", digest, root, stdin=paused(root, {}))
    assert code == 2 and "```output\nboom\n```" in verdict["reason"]
    assert counted(count) == 1


def test_the_paused_notice_promises_a_hold_only_where_done_still_fails(tmp_path: Path) -> None:
    """Breaks if the person is told that a failure found while paused is held at the first turn
    end that is not paused, when a turn that fixes it before then holds nothing."""

    count = tmp_path / "count"
    line = f"echo run >> {q(count)}; test -f fixed.txt || {{ echo boom; exit 1; }}"
    root, digest = target(tmp_path / "t", [line])
    stop = {**INPUT["claude-code"], "cwd": str(root), "background_tasks": [{"task_id": "b1"}]}
    assert hook("claude-code", digest, root, stdin=stop) == (0, {})
    prompt = {"session_id": "s", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}
    told = json.loads(mark("claude-code", digest, root, stdin=prompt).stdout)["systemMessage"]
    assert "while the session was paused" in told and "where Done still fails" in told, told

    write(root / "fixed.txt", "x\n")
    assert hook("claude-code", digest, root, stdin={**stop, "background_tasks": []}) == (0, {})
    assert counted(count) == 2


@pytest.mark.parametrize("waiting", WAITING, ids=["background-tasks", "session-crons"])
def test_background_work_leaves_a_tree_that_passed_silent(
    tmp_path: Path, waiting: dict[str, Any]
) -> None:
    """Breaks if a long wait on a tree Done already passed on prints anything or runs Done."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])
    assert hook("claude-code", digest, root) == (0, {})
    assert "finish-check PASS" in finish_helpers.status(root)

    for _ in range(3):
        assert hook("claude-code", digest, root, stdin=paused(root, waiting)) == (0, {})
    assert count.read_text(encoding="utf-8") == "run\n"


def test_an_unchanged_tree_reruns_nothing_and_a_changed_one_runs_again(tmp_path: Path) -> None:
    """Breaks if every turn end reruns the Done commands, or if a tracked edit or an untracked
    file is missed; the digest stays in the Git directory, out of the working tree."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])

    def runs() -> int:
        return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 1
    assert hook("codex", digest, root, run=False)[1] == {} and runs() == 1
    write(root / "src.txt", "two\n")
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 2
    write(root / "new.txt", "new\n")
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 3
    assert hook("codex", digest, root, run=False)[1] == {} and runs() == 3

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
    # The failure's own words name the tree, so that the changed tree's failure is a new one:
    # the same failure, in the same session, would go to the person (one hold per failure).
    line = f"echo run >> {q(count)}; cat src.txt; echo boom; exit 1"
    root, digest = target(tmp_path / "t", [line])

    def runs() -> int:
        return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0

    assert hook("codex", digest, root)[1]["decision"] == "block" and runs() == 1
    after_hold = {**INPUT["codex"], "cwd": str(root / "deeper"), "stop_hook_active": True}
    verdict = hook("codex", digest, root, stdin=after_hold, run=False)[1]
    assert list(verdict) == ["systemMessage"] and runs() == 1
    message = verdict["systemMessage"]
    assert message.startswith("finish-check FAIL: ")
    assert "unchanged since this failure, so it was not run again" in message
    assert "```output\none\nboom\n```" in message
    assert len(message) < finish_check.REPORT_CHARACTERS
    # Told once for the session and tree: later stops on it say nothing.
    for stdin in (after_hold, None):
        assert hook("codex", digest, root, stdin=stdin, run=False)[1] == {} and runs() == 1
    write(root / "src.txt", "two\n")
    assert hook("codex", digest, root)[1]["decision"] == "block" and runs() == 2

    # claude-code: the entry prints nothing and exits 0 on the repeat, and `--status` shows it.
    other, other_digest = target(tmp_path / "c", [line])
    assert hook("claude-code", other_digest, other)[0] == 2 and runs() == 3
    guarded = {**INPUT["claude-code"], "cwd": str(other), "stop_hook_active": True}
    shown = person("claude-code", other, hook("claude-code", other_digest, other, stdin=guarded)[1])
    assert "finish-check FAIL: " in shown and "not run again" in shown and runs() == 3


def test_an_unchanged_tree_that_timed_out_runs_again_only_under_a_longer_timeout(
    tmp_path: Path,
) -> None:
    """Breaks if a timed-out tree is run again, the limit spent, at every turn end, or if
    raising the timeout cannot get the same tree checked."""

    count = tmp_path / "count"
    # Done gets 15 seconds under the short timeout, so that Git's sh on a hosted Windows runner
    # still starts within it, and a sleep of 25 outlasts it but not the longer timeout.
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; sleep 25"])
    short = finish_check.MARGIN_SECONDS + 15

    def runs() -> int:
        return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0

    first = hook("codex", digest, root, timeout=short)[1]["systemMessage"]
    assert first.startswith("finish-check UNVERIFIED: ") and runs() == 1
    assert hook("codex", digest, root, timeout=short, run=False)[1] == {} and runs() == 1
    again = finish_helpers.status(root)
    assert "finish-check UNVERIFIED: " in again and runs() == 1
    longer = hook("codex", digest, root, timeout=short + 30)[1]["systemMessage"]
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
        # A run starts again on the same tree; the person was told once for this tree and kind.
        assert hook("codex", digest, root)[1] == {}
        record = finish_check.last_checked(root)
        assert record is not None and record.cause == finish_check.ENVIRONMENT
        assert "`no-such-tool-here --check` could not run" in finish_helpers.status(root)
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
    since = finish_helpers.now()
    assert stop_json("codex", digest, root) == {}
    finish_helpers.wait_for_run(root, since)

    since = finish_helpers.now()
    message = stop_json("codex", digest, root)["systemMessage"]
    assert message.startswith("finish-check UNVERIFIED: Done ran on a tree that changed")
    assert "Done, or something outside the session, writes into the tree" in message

    # The tree the run left was never checked, so that stop started a run on it, which changed
    # it again: no tree is ever read as checked.
    finish_helpers.wait_for_run(root, since)
    record = finish_check.last_checked(root)
    assert record is not None and record.kind == finish_check.CHANGED
    assert record.cause == finish_check.OUTSIDE
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
                "--constant-time",
                "--harness",
                "claude-code",
                "--done",
                digest,
                "--timeout",
                str(finish_check.MARGIN_SECONDS + 16),
            ],
            input=json.dumps({**INPUT["claude-code"], "cwd": str(root)}).encode(),
            cwd=root,
            capture_output=True,
            check=False,
            timeout=60,
        )
        assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")
        shown = finish_helpers.status(root)
        assert "PASS" in shown and "not remembered" in shown
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
    # The pid goes outside the tree, which the run reads again at its end: a tree the command
    # changed would be reported as such, not checked.
    holder = (
        "import os, subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "open(sys.argv[1], 'w').write(str(child.pid)); child.wait()"
    )
    write(tmp_path / "holder.py", holder + "\n")
    pid_file = tmp_path / "child.pid"
    line = f"{q(sys.executable)} {q(tmp_path / 'holder.py')} {q(pid_file)}"
    root, digest = target(tmp_path / "t", [line])
    limit = 15
    timeout = finish_check.MARGIN_SECONDS + limit
    started = time.monotonic()

    _, verdict = hook("codex", digest, root, cwd=root, timeout=timeout)

    assert time.monotonic() - started < limit + 25
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
    assert pid_file.exists(), f"the command never started: {message}"
    child = int(pid_file.read_text(encoding="utf-8"))
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

    _, verdict = hook(row, finish_check.done_digest(["true"]), empty, cwd=empty, run=False)

    assert f"no .outcomebound/manifest.json found from {empty}" in person(row, empty, verdict)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--harness", "gemini", "--done", "0" * 64],
        ["--harness", "codex", "--done", "short"],
        ["--harness", "codex"],
        ["--harness", "codex", "--done", "0" * 64, "--timeout", "30"],
        ["--harness", "codex", "--done", "0" * 64, "--timeout", "ten"],
        ["--constant-time", "--harness", "claude-code", "--done", "short"],
    ],
    ids=[
        "unavailable-row",
        "not-a-digest",
        "no-digest",
        "timeout-within-margin",
        "not-seconds",
        "wake-not-a-digest",
    ],
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
    verdict = hook("codex", finish_check.done_digest(done), root, run=False)[1]
    message = verdict["systemMessage"]
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
    message = hook("codex", digest, root, run=False)[1]["systemMessage"]
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


def turn(row: str, digest: str, root: Path, stdin: dict[str, Any] | None = None) -> str:
    """The prompt that begins a turn: the mark runs and succeeds, writing nothing to standard
    error. On codex it prints nothing; on claude-code it prints nothing, or one JSON object with
    the person's notices as its `systemMessage` and nothing else, which is returned."""

    done = mark(row, digest, root, stdin=stdin)
    assert (done.returncode, done.stderr) == (0, b""), done
    if row == "codex" or not done.stdout:
        assert done.stdout == b"", done.stdout
        return ""
    printed = json.loads(done.stdout)
    assert list(printed) == ["systemMessage"], printed
    return str(printed["systemMessage"])


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
    verdict = hook(row, digest, root, run=False)[1]

    message = person(row, root, verdict)
    assert counted(count) == 0
    if row == "codex":
        assert message.startswith("finish-check: the tree is the one this turn began with (marked ")
        assert message.endswith("); Done was not run.")
    else:
        assert "finish-check: the tree is the one this turn began with (marked " in message
        assert "); Done was not run." in message
    # The turn's end stamped the mark: it is kept, and the next prompt writes a fresh one.
    kept = json.loads((root / ".git" / finish_check.MARK).read_text(encoding="utf-8"))
    assert finish_check.stamp(kept.get("ended")) is not None
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
    line = f"echo run >> {q(count)}; echo boom; exit 1"
    root, digest = target(tmp_path / "t", [line])
    assert hook("codex", digest, root)[1]["decision"] == "block" and counted(count) == 1

    turn("codex", digest, root)
    verdict = hook("codex", digest, root, run=False)[1]

    assert list(verdict) == ["systemMessage"] and counted(count) == 1
    assert "so it was not run again" in verdict["systemMessage"]
    assert "(marked " in verdict["systemMessage"]

    # claude-code: the entry prints nothing and exits 0, and `--status` shows the same.
    other, other_digest = target(tmp_path / "c", [line])
    assert hook("claude-code", other_digest, other)[0] == 2 and counted(count) == 2
    turn("claude-code", other_digest, other)
    shown = person("claude-code", other, hook("claude-code", other_digest, other)[1])
    assert "so it was not run again" in shown and "(marked " in shown and counted(count) == 2


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

    message = person(row, root, verdict)
    assert "finish-check FAIL, known before this turn: " in message
    if row == "codex":
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
    # A new failure each time: the same one again in the session goes to the person.
    write(root / "src.txt", "two\n")
    write(flags / "second", "")
    assert hook(row, digest, root)[1]["decision"] == "block"

    other, other_digest = target(tmp_path / "other", ["exit 1"])
    turn(row, other_digest, other)
    (other / ".git" / finish_check.MARK).replace(root / ".git" / finish_check.MARK)
    write(root / "src.txt", "three\n")
    write(flags / "third", "")
    assert hook(row, digest, root)[1]["decision"] == "block"


def test_an_unreadable_mark_is_no_mark(tmp_path: Path) -> None:
    """Breaks if a mark the verb cannot read, or one that names the head and tree of another
    state, stops the check from running: the check then behaves as with no mark."""

    count = tmp_path / "count"
    # The output names the tree, so that each turn's failure is a new one in the session.
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; cat src.txt; exit 1"])
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

    unchanged = hook(row, digest, root, transcript="none", run=False)[1]
    assert "Done was not run" in person(row, root, unchanged)
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

    unchanged = person(row, root, hook(row, digest, root, run=False)[1])
    assert f"(marked {clock})" in unchanged and "not run again" in unchanged

    turn(row, digest, root)
    clock = mark_time(root).astimezone().strftime("%H:%M:%S")
    write(root / "src.txt", "two\n")
    known = person(row, root, hook(row, digest, root)[1])
    assert f"(marked {clock})" in known and "finish-check FAIL, known before" in known
    if row == "codex":
        assert known.startswith("finish-check FAIL, known before")


@pytest.mark.parametrize("row", ROWS)
def test_an_unchanged_turn_is_told_once_for_a_session_and_tree(tmp_path: Path, row: str) -> None:
    """Breaks if a session that only reads is told "Done was not run" after every reply, or if a
    changed tree or another session is not told again."""

    root, digest = target(tmp_path / "t", ["true"])
    if row == "claude-code":
        # The entry prints nothing and exits 0 at each unchanged turn end, and `--status` shows
        # what codex's message shows; the turn-start entry tells it once (its own test).
        for _ in range(2):
            turn(row, digest, root)
            assert hook(row, digest, root) == (0, {})
            assert "Done was not run" in finish_helpers.status(root)
        return

    turn(row, digest, root)
    assert "Done was not run" in hook(row, digest, root, run=False)[1]["systemMessage"]
    turn(row, digest, root)
    assert hook(row, digest, root, run=False)[1] == {}

    write(root / "src.txt", "two\n")
    turn(row, digest, root)
    assert "Done was not run" in hook(row, digest, root, run=False)[1]["systemMessage"]
    turn(row, digest, root)
    assert hook(row, digest, root, run=False)[1] == {}

    other = {"session_id": "another", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}
    assert mark(row, digest, root, stdin=other).returncode == 0
    stop = {**INPUT[row], "cwd": str(root), "session_id": "another", "transcript_path": None}
    assert "Done was not run" in hook(row, digest, root, stdin=stop, run=False)[1]["systemMessage"]


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

    assert "PASS" in person(row, root, verdict) and counted(count) == 1


@pytest.mark.parametrize("row", ROWS)
def test_a_held_turn_compares_with_its_stamped_mark(tmp_path: Path, row: str) -> None:
    """Breaks if a hold moves the baseline past the turn's edits: on claude-code the run
    stamps the mark and then wakes the model, and the woken turn's end must still compare with
    the tree the turn began with; on codex the prompt a hold creates must leave the turn's mark.
    The retry, its failure already held, tells the person and holds nothing."""

    root, digest, flags = suite(tmp_path)
    write(flags / "old", "")
    assert hook(row, digest, root)[1]["decision"] == "block"
    turn(row, digest, root)
    began = mark_time(root)
    write(root / "src.txt", "two\n")
    write(flags / "new", "")

    if row == "claude-code":
        assert hook(row, digest, root)[1]["decision"] == "block"
    else:
        # codex delivers at a later turn's stop: the turn that ends here starts the run, and the
        # next turn, which changes nothing, is held; the prompt that hold creates keeps its mark.
        assert hook(row, digest, root, run=False)[1] == {}
        finish_helpers.wait_for_run(root, began)
        turn(row, digest, root)
        began = mark_time(root)
        assert hook(row, digest, root, run=False)[1]["decision"] == "block"
        turn(row, digest, root)
    assert mark_time(root) == began
    write(root / "src.txt", "three\n")
    retry = stop_input(row, root, stop_hook_active=True)
    verdict = hook(row, digest, root, stdin=retry)[1]

    message = person(row, root, verdict)
    assert "tests/new.py::test_x" in message
    assert "known before this turn" in message or "held once already" in message
    assert mark_time(root) == began


@pytest.mark.parametrize("row", ROWS)
def test_the_turn_end_stamps_the_mark_ended_and_the_next_prompt_writes_a_fresh_one(
    tmp_path: Path, row: str
) -> None:
    """Breaks if the turn's end deletes the mark (a run that starts after it then has no
    baseline) or leaves it live (the next prompt then keeps it, and a later turn compares with a
    tree it did not begin with)."""

    root, digest = target(tmp_path / "t", ["true"])
    turn(row, digest, root)
    path = root / ".git" / finish_check.MARK
    first = json.loads(path.read_text(encoding="utf-8"))
    assert "ended" not in first

    hook(row, digest, root, run=False)

    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert {k: v for k, v in stamped.items() if k != "ended"} == first
    assert finish_check.stamp(stamped["ended"]) is not None
    write(root / "src.txt", "two\n")
    turn(row, digest, root)
    fresh = json.loads(path.read_text(encoding="utf-8"))
    assert "ended" not in fresh and fresh["tree"] != first["tree"]
    later, earlier = finish_check.stamp(fresh["time"]), finish_check.stamp(first["time"])
    assert later is not None and earlier is not None and later >= earlier


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
    assert hook("claude-code", digest, root, stdin=control) == (0, {})
    assert "Done was not run" in finish_helpers.status(root)

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


def pytest_output(skipped: int, padding: int) -> str:
    """Output shaped as pytest with `-rs` prints it: a traceback, long output after it, the
    short summary with failures, then the skips last."""

    lines = ["E   OSError: [Errno 28] No space left on device"]
    lines += [f"{'x' * 60} {n}" for n in range(padding)]
    lines += ["=== short test summary info ===", "FAILED tests/test_a.py::test_one - OSError"]
    lines += ["ERROR tests/test_b.py::test_two - OSError"]
    lines += [f"SKIPPED [1] tests/test_s.py:{n}: not here" for n in range(skipped)]
    lines += ["1 failed, 1 error, 60 skipped"]
    return "\n".join(lines) + "\n"


def test_the_hold_shows_the_failures_and_the_cause_not_the_skips(tmp_path: Path) -> None:
    """Breaks if `SKIPPED` lines from `-rs` fill the shown tail while pytest names failures, or
    if the failure ids and the first traceback line that the tail cut off are not shown."""

    write(tmp_path / "out.txt", pytest_output(skipped=60, padding=200))
    root, digest = target(tmp_path / "t", [f"cat {q(tmp_path / 'out.txt')}; exit 1"])

    reason = hook("codex", digest, root)[1]["reason"]

    assert "SKIPPED" not in reason
    assert "FAILED tests/test_a.py::test_one - OSError" in reason
    assert "ERROR tests/test_b.py::test_two" in reason
    assert "E   OSError: [Errno 28] No space left on device" in reason
    assert len(reason) < finish_check.REPORT_CHARACTERS


def test_skips_stay_where_no_runner_names_a_failure(tmp_path: Path) -> None:
    """Breaks if lines starting with SKIPPED are dropped from output that names no failure."""

    write(tmp_path / "out.txt", "SKIPPED [1] a: b\nboom\n")
    root, digest = target(tmp_path / "t", [f"cat {q(tmp_path / 'out.txt')}; exit 1"])

    assert "SKIPPED [1] a: b" in hook("codex", digest, root)[1]["reason"]


def test_failure_ids_above_the_kept_tail_are_still_read(tmp_path: Path) -> None:
    """Breaks if only the last 64 KiB of output is searched for failure ids: ids printed before
    the tail would be lost, and a new failure among them would look known."""

    names = ["tests/test_a.py::test_one", "tests/test_a.py::test_two"]
    body = "".join(f"FAILED {name} - boom\n" for name in names)
    body += "y" * 100 + "\n"
    body += ("z" * 99 + "\n") * 2000
    assert len(body) > finish_check.TAIL_BYTES + 100_000
    write(tmp_path / "out.txt", body)
    root, _ = target(tmp_path / "t", ["true"])

    result = finish_check.run_one(root, f"cat {q(tmp_path / 'out.txt')}; exit 1", 60)

    assert not finish_check.failure_ids(result.output)
    assert result.ids == {f"pytest {name}" for name in names}
    again = finish_check.Result.of(result.document())
    assert again is not None and again.ids == result.ids


def test_a_scan_of_failure_ids_that_stopped_early_never_makes_a_failure_known(
    tmp_path: Path,
) -> None:
    """Breaks if a scan that stopped at the id cap, or at its time limit, reads as every id the
    output named: a new failure printed after the cap and above the kept tail would look known,
    and the report would say no named failure is new."""

    old = "".join(
        f"FAILED tests/test_old.py::test_{n} - old\n" for n in range(finish_check.MAX_IDS)
    )
    pad = ("z" * 99 + "\n") * 2200
    out = tmp_path / "out.txt"
    root, _ = target(tmp_path / "t", ["true"])
    line = f"cat {q(out)}; exit 1"
    write(out, old + pad)
    before = finish_check.run_one(root, line, 60)
    write(out, old + "FAILED tests/test_new.py::test_new - new\n" + pad)
    after = finish_check.run_one(root, line, 60)

    known = finish_check.Failure(1, finish_check.result_ids(before))
    tolerated, why = known.tolerates(after)
    assert not tolerated and "not known" in why, why
    again = finish_check.Result.of(after.document())
    assert again is not None and not known.tolerates(again)[0]

    with open(out, "rb") as sink:
        ids, complete = finish_check._ids_in(sink, time.monotonic() - 1)
    assert not ids and not complete


def test_a_hold_says_where_a_command_was_compared_by_its_exit_code_alone(tmp_path: Path) -> None:
    """Breaks if a hold hides that a known command was compared by exit code only, which is
    weaker than comparing failure ids."""

    broken = tmp_path / "broken"
    done = ["echo old; exit 1", f"test ! -e {q(broken)} || {{ echo new; exit 4; }}"]
    root, digest = target(tmp_path / "t", done)
    assert finish_check.measure(root, done, 600).kept
    write(broken, "")
    write(root / "src.txt", "two\n")

    reason = hook("codex", digest, root)[1]["reason"]

    assert reason.startswith("finish-check FAIL: ")
    assert "compared by that code alone" in reason


def test_a_hold_names_the_environment_done_ran_with(tmp_path: Path) -> None:
    """Breaks if a hold leaves the agent unable to tell a failure of the hook's environment
    from a real one: where Done ran and the PATH in front."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])

    reason = hook("codex", digest, root)[1]["reason"]

    assert "Done ran from " in reason and " with PATH starting " in reason


# --- The constant-time stop: who runs Done, and who hears of it --------------------

CC = "claude-code"


def wait_for(path: Path, seconds: float = 60) -> None:
    """Wait for a file a Done command writes when it reaches a point."""

    deadline = time.monotonic() + seconds
    while not path.exists():
        assert time.monotonic() < deadline, f"{path} never appeared"
        time.sleep(0.05)


def gated(tmp_path: Path, name: str = "gate") -> tuple[Path, Path, str]:
    """A Done fragment that writes `started` and waits, a minute at most, for `go`; both are
    outside the tree, so that a test can act while the command runs."""

    started, go = tmp_path / f"{name}-started", tmp_path / f"{name}-go"
    line = (
        f"touch {q(started)}; i=0; while [ ! -e {q(go)} ] && [ $i -lt 600 ]; "
        "do sleep 0.1; i=$((i+1)); done"
    )
    return started, go, line


def finished(process: Any, seconds: float = 120) -> tuple[int, bytes, bytes]:
    out, err = process.communicate(timeout=seconds)
    return process.returncode, out, err


def stop_json(row: str, digest: str, root: Path, **options: Any) -> dict[str, Any]:
    """One codex stop's JSON, as it prints it, with no wait for the run it may start."""

    done = fire(row, digest, root, **options)
    assert isinstance(done, subprocess.CompletedProcess)
    assert done.returncode == 0, done.stderr.decode()
    printed: dict[str, Any] = json.loads(done.stdout)
    return printed


def clock(text: str) -> str:
    when = finish_check.stamp(text)
    assert when is not None
    return when.astimezone().strftime("%H:%M:%S")


def other_session(row: str, root: Path, **fields: Any) -> dict[str, Any]:
    working = root / "deeper" if row == "codex" else root
    working.mkdir(exist_ok=True)
    return {
        **INPUT[row],
        "cwd": str(working),
        "session_id": "another",
        "transcript_path": None,
        **fields,
    }


def end_run(root: Path, since: datetime) -> None:
    """Stop the background run that started at or after `since`, and wait until it is gone."""

    record = finish_helpers.wait_for_run(root, since, ended=False)
    pid = int(record["pid"])
    programs.terminate(pid)
    deadline = time.monotonic() + 30
    while programs.alive(pid):
        assert time.monotonic() < deadline, f"the run {pid} outlived its stop"
        time.sleep(0.1)


def test_the_claude_code_entry_runs_done_in_its_own_process_and_exits_2_only_on_a_holding_failure(
    tmp_path: Path,
) -> None:
    """Breaks if the claude-code entry hands Done to another process, so that the wake has no
    verdict to carry; if it prints anything on a pass, which an async hook sends to the model on
    its next turn; or if it exits 2 on anything but a failure that holds."""

    count, broken = tmp_path / "count", tmp_path / "broken"
    line = f"echo run >> {q(count)}; test ! -e {q(broken)} || {{ echo boom; exit 1; }}"
    root, digest = target(tmp_path / "t", [line])

    process = fire(CC, digest, root, background=True)
    assert finished(process) == (0, b"", b"") and counted(count) == 1
    record = finish_helpers.run_record(root)
    assert record is not None and record["pid"] == process.pid
    assert record["ended"]["outcome"] == "pass"

    write(broken, "")
    write(root / "src.txt", "two\n")
    process = fire(CC, digest, root, background=True)
    code, out, err = finished(process)
    assert (code, out) == (2, b"") and counted(count) == 2
    assert err.decode().startswith("finish-check FAIL: ")
    assert "```output\nboom\n```" in err.decode()
    record = finish_helpers.run_record(root)
    assert record is not None and record["pid"] == process.pid


def test_the_codex_stop_returns_before_a_slow_done_command_ends(tmp_path: Path) -> None:
    """Breaks if the codex stop waits for Done: the person waited 3 to 5 minutes at each turn
    end that changed the tree. The run it starts names the tree it checks."""

    root, digest = target(tmp_path / "t", ["sleep 60"])
    since = finish_helpers.now()
    begun = time.monotonic()

    printed = stop_json("codex", digest, root)

    assert time.monotonic() - begun < 5 and printed == {}
    record = finish_helpers.wait_for_run(root, since, ended=False)
    assert record["tree"] == finish_check.tree_digest(root, digest) and "ended" not in record
    end_run(root, since)


def test_the_codex_stop_prints_its_json_and_closes_stdout_before_the_run_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the stop starts the run before its verdict is out and its output closed: the
    harness reads the stop's output to its end, and a run holding it open would make the turn
    end wait for Done."""

    root, digest = target(tmp_path / "t", ["true"])
    seen: list[tuple[str, Any]] = []

    class Out(io.BytesIO):
        def close(self) -> None:
            seen.append(("closed", self.getvalue()))
            super().close()

    out = Out()
    given = json.dumps({**INPUT["codex"], "cwd": str(root), "transcript_path": None}).encode()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, encoding="utf-8"))
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(given)))
    monkeypatch.setattr(
        finish_check.programs,
        "start_detached",
        lambda argv, **options: seen.append(("started", out.closed)),
    )
    monkeypatch.chdir(root)

    assert finish_check.main(["--constant-time", "--harness", "codex", "--done", digest]) == 0

    assert seen in (
        [("closed", b"{}\n"), ("started", True)],
        [("closed", b"{}\r\n"), ("started", True)],
    )


class Kept(io.BytesIO):
    """Standard output for a stop run in this process: what it printed stays readable after the
    stop closes it."""

    def close(self) -> None:
        pass


def test_the_delivery_follows_the_wake_field_of_the_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if the delivery follows the row's name or a flag rather than the harness table's
    `wake` field: with the fields swapped, codex's entry runs Done in itself and exits 2, and
    claude-code's prints its JSON and starts the run."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    table = copy.deepcopy(adapters.table())
    table["codex"]["finish_hook"]["wake"] = table[CC]["finish_hook"]["wake"]
    table[CC]["finish_hook"]["wake"] = None
    monkeypatch.setattr(finish_check.adapters, "table", lambda: table)
    started: list[list[str]] = []
    monkeypatch.setattr(
        finish_check.programs, "start_detached", lambda argv, **options: started.append(argv)
    )
    monkeypatch.chdir(root)

    def entry(row: str) -> int:
        given = json.dumps({**INPUT[row], "cwd": str(root), "transcript_path": None}).encode()
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(given)))
        return finish_check.main(["--constant-time", "--harness", row, "--done", digest])

    assert entry("codex") == 2
    out, err = capsys.readouterr()
    assert out == "" and err.startswith("finish-check FAIL: ") and started == []

    write(root / "src.txt", "two\n")
    printed = Kept()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(printed, encoding="utf-8"))
    assert entry(CC) == 0
    assert json.loads(printed.getvalue()) == {}
    assert len(started) == 1 and "--run" in started[0]


def test_a_slow_tree_read_still_runs_done(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Breaks if the run reads the tree within the stop's budget, so that a checkout whose tree
    takes longer to read than a stop may wait is never checked."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])
    real = finish_check.tree_digest

    def slow(*arguments: Any, **options: Any) -> str | None:
        time.sleep(0.5)
        return real(*arguments, **options)

    monkeypatch.setattr(finish_check, "STOP_READ_SECONDS", 0.1)
    monkeypatch.setattr(finish_check, "tree_digest", slow)
    given = json.dumps({**INPUT[CC], "cwd": str(root), "transcript_path": None}).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(given)))
    monkeypatch.chdir(root)

    assert finish_check.main(["--constant-time", "--harness", CC, "--done", digest]) == 0

    record = finish_check.last_checked(root)
    assert counted(count) == 1 and record is not None and record.verdict == finish_check.PASS


def test_a_run_whose_tree_changes_keeps_its_results_as_an_unverified_record_of_its_start_tree(
    tmp_path: Path,
) -> None:
    """Breaks if a run whose tree changed while Done ran (the person typed and the agent edited)
    discards its results, which leaves the next turn with no baseline in exactly the flow the
    constant-time stop is for, or records them as a check of a tree."""

    started, go, gate = gated(tmp_path)
    root, digest = target(tmp_path / "t", ["true", f"{gate}; echo boom; exit 1"])
    start_tree = finish_check.tree_digest(root, digest)
    process = fire(CC, digest, root, background=True)
    wait_for(started)
    turn(CC, digest, root)
    write(root / "src.txt", "two\n")
    write(go, "")

    assert finished(process) == (0, b"", b"")

    record = finish_check.checked_for(root, start_tree)
    assert record is not None and record.kind == finish_check.CHANGED
    assert record.verdict == finish_check.UNVERIFIED and record.session == "s"
    assert [r.verdict for r in record.results] == [finish_check.PASS, finish_check.FAIL]
    assert record.cause == ""
    assert finish_check.checked_for(root, finish_check.tree_digest(root, digest)) is None


@posix_only
def test_a_superseded_run_keeps_the_results_of_the_commands_that_ended(tmp_path: Path) -> None:
    """Breaks if a run that a turn end on another tree superseded loses what its finished
    commands found, or reads as a check. POSIX: on Windows the run is ended with
    TerminateProcess, which runs none of its code."""

    started, go, gate = gated(tmp_path)
    root, digest = target(tmp_path / "t", ["true", gate])
    first_tree = finish_check.tree_digest(root, digest)
    holder = fire(CC, digest, root, background=True)
    wait_for(started)
    write(root / "src.txt", "two\n")
    started.unlink()

    superseder = fire(CC, digest, root, background=True)

    assert finished(holder, 60) == (0, b"", b"")
    record = finish_check.checked_for(root, first_tree)
    assert record is not None and record.kind == finish_check.CHANGED
    assert record.cause == finish_check.SUPERSEDED
    assert [r.verdict for r in record.results] == [finish_check.PASS]
    wait_for(started)
    write(go, "")
    assert finished(superseder) == (0, b"", b"")


def test_a_run_records_the_tree_head_session_and_mark_it_started_with(tmp_path: Path) -> None:
    """Breaks if the run record cannot say which tree and session a verdict is for, which mark
    it compared with, or whether its process lives."""

    root, digest = target(tmp_path / "t", ["true"])
    turn(CC, digest, root)
    marked_with = json.loads((root / ".git" / finish_check.MARK).read_text(encoding="utf-8"))
    write(root / "src.txt", "two\n")
    tree = finish_check.tree_digest(root, digest)
    head = subprocess.run(
        [GIT, "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    process = fire(CC, digest, root, background=True)
    assert finished(process) == (0, b"", b"")

    record = finish_helpers.run_record(root)
    assert record is not None
    assert (record["pid"], record["tree"], record["head"]) == (process.pid, tree, head)
    assert record["session"] == "s" and record["done"] == digest and record["timeout"] == 600
    assert record["mark"] == {"tree": marked_with["tree"], "time": marked_with["time"]}
    assert finish_check.stamp(record["started"]) is not None
    assert record["ended"]["outcome"] == "pass"


@pytest.mark.parametrize(
    "case", ["pass", "fail", "unverified", "changed", "unchanged", "recorded", "error"]
)
def test_every_exit_of_the_run_writes_ended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Breaks if an exit of the run leaves its record without `ended`: a stop would read a run
    that ended as one still running, or as a run that died."""

    lines = {
        "pass": ["true"],
        "fail": ["echo boom; exit 1"],
        "unverified": ["no-such-tool-here-zz"],
        "changed": ["echo again >> grows.txt"],
        "unchanged": ["true"],
        "recorded": ["true"],
        "error": ["true"],
    }
    root, digest = target(tmp_path / "t", lines[case])
    if case == "unchanged":
        turn(CC, digest, root)
    if case == "recorded":
        assert hook(CC, digest, root) == (0, {})
    if case == "error":

        def broken(*arguments: Any, **options: Any) -> list[finish_check.Result]:
            raise RuntimeError("synthetic")

        monkeypatch.setattr(finish_check, "run_all", broken)
        given = json.dumps({**INPUT[CC], "cwd": str(root), "transcript_path": None}).encode()
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(given)))
        monkeypatch.chdir(root)
        assert finish_check.main(["--constant-time", "--harness", CC, "--done", digest]) == 0
    else:
        hook(CC, digest, root)

    record = finish_helpers.run_record(root)
    assert record is not None and finish_check.stamp(record["ended"]["time"]) is not None
    assert record["ended"]["outcome"].startswith(case), record["ended"]


def test_a_detached_run_outlives_the_codex_stop_that_started_it(tmp_path: Path) -> None:
    """Breaks if the run dies with the stop that started it: on codex no run would ever end, and
    every stop would read a dead run."""

    ran = tmp_path / "ran"
    root, digest = target(tmp_path / "t", [f"sleep 3; touch {q(ran)}"])
    since = finish_helpers.now()

    assert stop_json("codex", digest, root) == {}
    assert not ran.exists()

    record = finish_helpers.wait_for_run(root, since)
    assert ran.exists() and record["ended"]["outcome"] == "pass"


def test_the_wake_exits_0_and_prints_nothing_on_a_pass_a_known_failure_and_a_changed_tree(
    tmp_path: Path,
) -> None:
    """Breaks if anything but a holding failure writes to either stream: an async hook's output
    goes to the model on its next turn."""

    root, digest = target(tmp_path / "pass", ["true"])
    assert hook(CC, digest, root) == (0, {})

    done = ["echo old; exit 1"]
    root, digest = target(tmp_path / "known", done)
    assert finish_check.measure(root, done, 600).kept
    write(root / "src.txt", "two\n")
    assert hook(CC, digest, root) == (0, {})
    assert "finish-check FAIL, known: " in finish_helpers.status(root)

    root, digest = target(tmp_path / "changed", ["echo again >> grows.txt; exit 1"])
    assert hook(CC, digest, root) == (0, {})
    record = finish_check.last_checked(root)
    assert record is not None and record.kind == finish_check.CHANGED


def test_the_wake_never_exits_2_when_stop_hook_active_is_set(tmp_path: Path) -> None:
    """Breaks if a wake's own turn end, which has the guard set, wakes the model again: one
    retry per finish. Done still runs, and the person reads the failure."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])
    guarded = {**INPUT[CC], "cwd": str(root), "stop_hook_active": True}

    assert hook(CC, digest, root, stdin=guarded) == (0, {}) and counted(count) == 1
    assert "finish-check FAIL" in finish_helpers.status(root)


@pytest.mark.parametrize("waiting", WAITING, ids=["background-tasks", "session-crons"])
def test_the_wake_never_exits_2_while_the_session_is_paused(
    tmp_path: Path, waiting: dict[str, Any]
) -> None:
    """Breaks if a paused session, whose background work will wake it, is woken for a failure,
    or if Done is skipped while it waits."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])

    assert hook(CC, digest, root, stdin=paused(root, waiting)) == (0, {})
    assert counted(count) == 1


@pytest.mark.parametrize("how", ["prompt", "same-second", "clock-back"])
def test_a_live_mark_of_the_session_at_the_runs_end_leaves_the_failure_to_the_next_stop(
    tmp_path: Path, how: str
) -> None:
    """Breaks if a wake lands in the middle of the next task the person typed while Done ran,
    or if that is decided by comparing clocks: a mark written in the same second as the run's
    end, and one whose time a clock moved back, still defer, since the mark is live. The next
    stop delivers the failure without running Done again."""

    started, go, gate = gated(tmp_path)
    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; {gate}; echo boom; exit 1"])
    turn(CC, digest, root)
    write(root / "src.txt", "two\n")
    process = fire(CC, digest, root, background=True)
    wait_for(started)
    path = root / ".git" / finish_check.MARK
    if how == "prompt":
        turn(CC, digest, root)
    else:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        when = now if how == "same-second" else now - timedelta(hours=1)
        document = json.loads(path.read_text(encoding="utf-8"))
        document.pop("ended", None)
        write(path, json.dumps({**document, "time": when.isoformat()}) + "\n")
    write(go, "")

    assert finished(process) == (0, b"", b"")

    code, verdict = hook(CC, digest, root)
    assert code == 2 and "```output\nboom\n```" in verdict["reason"]
    assert counted(count) == 1


def test_the_run_stamps_only_a_mark_of_its_own_session(tmp_path: Path) -> None:
    """Breaks if a run ends another session's turn, which would then lose its own start."""

    root, digest = target(tmp_path / "t", ["true"])
    other = {"session_id": "another", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}
    turn(CC, digest, root, stdin=other)
    path = root / ".git" / finish_check.MARK
    before = path.read_bytes()
    write(root / "src.txt", "two\n")

    assert hook(CC, digest, root) == (0, {})

    assert path.read_bytes() == before


def test_a_woken_failure_is_not_held_again_at_the_next_stop(tmp_path: Path) -> None:
    """Breaks if a failure the wake delivered holds again, at the woken turn's end or at a later
    stop of the session, on the same tree or another."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])
    assert hook(CC, digest, root)[0] == 2
    woken = {**INPUT[CC], "cwd": str(root), "stop_hook_active": True}

    assert hook(CC, digest, root, stdin=woken) == (0, {})
    assert hook(CC, digest, root) == (0, {})
    write(root / "src.txt", "two\n")
    assert hook(CC, digest, root) == (0, {}) and counted(count) == 2


@pytest.mark.parametrize("row", ROWS)
def test_a_recorded_failure_on_the_unchanged_tree_is_delivered_at_once(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a failure no wake delivered, on the tree it was found on, waits for another
    run, or runs Done again: the record is that tree's own verdict."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])
    if row == "codex":
        since = finish_helpers.now()
        assert stop_json(row, digest, root) == {}
        finish_helpers.wait_for_run(root, since)
    else:
        assert hook(row, digest, root, stdin=paused(root, WAITING[0])) == (0, {})

    _, verdict = hook(row, digest, root, run=False)

    assert verdict["decision"] == "block" and "boom" in verdict["reason"]
    assert counted(count) == 1


def deferred(tmp_path: Path, root: Path, digest: str, started: Path, go: Path) -> None:
    """A claude-code run whose failure is left to the next stop: the person types while Done
    runs, so a new turn begins before it ends."""

    process = fire(CC, digest, root, background=True)
    wait_for(started)
    turn(CC, digest, root)
    write(go, "")
    assert finished(process) == (0, b"", b"")
    started.unlink()


def test_on_claude_code_a_failure_on_a_changed_tree_holds_only_after_a_run_finds_it_again(
    tmp_path: Path,
) -> None:
    """Breaks if a failure no wake delivered wakes the model at once on a tree the next turn
    changed, which its change may have fixed, or is lost: the run on the new tree finds it again
    and holds it, naming when it was first found."""

    started, go, gate = gated(tmp_path)
    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; {gate}; echo boom; exit 1"])
    turn(CC, digest, root)
    write(root / "src.txt", "two\n")
    deferred(tmp_path, root, digest, started, go)
    first = finish_check.last_checked(root)
    assert first is not None and first.verdict == finish_check.FAIL
    write(root / "src.txt", "three\n")

    code, verdict = hook(CC, digest, root)

    assert code == 2 and counted(count) == 2
    assert verdict["reason"].startswith(
        f"finish-check FAIL: Done failed on the tree this turn began with, at {clock(first.time)}, "
        "and still fails now"
    )


def test_on_claude_code_an_undelivered_failure_the_turn_fixed_is_never_held(
    tmp_path: Path,
) -> None:
    """Breaks if a failure the next turn's edits fixed reaches the model at all."""

    started, go, gate = gated(tmp_path)
    broken = tmp_path / "broken"
    write(broken, "")
    root, digest = target(
        tmp_path / "t", [f"{gate}; test ! -e {q(broken)} || {{ echo boom; exit 1; }}"]
    )
    turn(CC, digest, root)
    write(root / "src.txt", "two\n")
    deferred(tmp_path, root, digest, started, go)
    broken.unlink()
    write(root / "src.txt", "three\n")

    assert hook(CC, digest, root) == (0, {})
    assert hook(CC, digest, root) == (0, {})


def test_on_codex_an_undelivered_failure_holds_one_stop_later_with_the_times_of_both_runs(
    tmp_path: Path,
) -> None:
    """Breaks if codex's stop holds on a record of the tree its turn began on before a run has
    found the failure again, or never holds it: the stop after the confirming run holds it, with
    the time of each run."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; echo boom; exit 1"])
    turn("codex", digest, root)
    write(root / "src.txt", "two\n")
    since = finish_helpers.now()
    assert hook("codex", digest, root, run=False)[1] == {}
    finish_helpers.wait_for_run(root, since)
    first = finish_check.last_checked(root)
    assert first is not None

    turn("codex", digest, root)
    write(root / "src.txt", "three\n")
    since = finish_helpers.now()
    assert "decision" not in hook("codex", digest, root, run=False)[1]
    finish_helpers.wait_for_run(root, since)
    second = finish_check.last_checked(root)
    assert second is not None and counted(count) == 2

    turn("codex", digest, root)
    write(root / "src.txt", "four\n")
    since = finish_helpers.now()
    verdict = hook("codex", digest, root, run=False)[1]
    finish_helpers.wait_for_run(root, since)

    assert verdict["decision"] == "block"
    head = verdict["reason"].splitlines()[0]
    assert f"at {clock(first.time)}, and still fails now" in head and clock(second.time) in head


@pytest.mark.parametrize("row", ROWS)
def test_a_failure_another_session_recorded_is_never_held(tmp_path: Path, row: str) -> None:
    """Breaks if a session's turn, perhaps one that changed nothing, is held for a failure
    another session's run found."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    since = finish_helpers.now()
    assert stop_json("codex", digest, root, stdin=other_session("codex", root)) == {}
    finish_helpers.wait_for_run(root, since)

    _, verdict = hook(row, digest, root, run=False)

    assert "decision" not in verdict and "finish-check FAIL" in person(row, root, verdict)


@pytest.mark.parametrize("row", ROWS)
def test_a_turn_that_makes_a_tree_another_session_saw_fail_is_held(tmp_path: Path, row: str) -> None:
    """Breaks if another session's failure record on the tree this turn made stands in for
    this turn's own run: the turn changed the tree, so it may have caused the failure."""

    root, digest = target(tmp_path / "t", ["test ! -e broken || { echo boom; exit 1; }"])
    write(root / "broken", "x\n")
    since = finish_helpers.now()
    assert stop_json("codex", digest, root, stdin=other_session("codex", root)) == {}
    finish_helpers.wait_for_run(root, since)
    (root / "broken").unlink()

    turn(row, digest, root)
    write(root / "broken", "x\n")
    _, verdict = hook(row, digest, root)

    assert verdict.get("decision") == "block" and "boom" in verdict["reason"]


@pytest.mark.parametrize("row", ROWS)
def test_a_recorded_failure_on_an_older_tree_is_never_held(tmp_path: Path, row: str) -> None:
    """Breaks if a failure recorded on a tree that has changed since is held without a run
    that finds it again."""

    broken = tmp_path / "broken"
    write(broken, "")
    root, digest = target(tmp_path / "t", [f"test ! -e {q(broken)} || {{ echo boom; exit 1; }}"])
    since = finish_helpers.now()
    assert stop_json("codex", digest, root) == {}
    finish_helpers.wait_for_run(root, since)
    broken.unlink()
    write(root / "src.txt", "two\n")

    _, verdict = hook(row, digest, root)

    assert "decision" not in verdict
    assert "finish-check PASS" in person(row, root, verdict)


def test_a_follower_on_the_running_tree_waits_for_the_holder_and_delivers_under_its_own_input(
    tmp_path: Path,
) -> None:
    """Breaks if a second run on the tree a run is checking starts Done again, or exits before
    the verdict: the holder's input had the guard set and cannot deliver, so the follower must,
    under its own."""

    started, go, gate = gated(tmp_path)
    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; {gate}; echo boom; exit 1"])
    guarded = {**INPUT[CC], "cwd": str(root), "stop_hook_active": True, "transcript_path": None}
    holder = fire(CC, digest, root, stdin=guarded, background=True)
    wait_for(started)

    follower = fire(CC, digest, root, background=True)
    time.sleep(1)
    assert follower.poll() is None
    write(go, "")

    assert finished(holder) == (0, b"", b"")
    code, out, err = finished(follower)
    assert (code, out) == (2, b"") and "boom" in err.decode() and counted(count) == 1


def outputs(row: str, digest: str, root: Path, **options: Any) -> list[Any]:
    """Every stop a turn end takes, as printed: codex's JSON of each stop (the one that starts
    the run, and the one after it ends), claude-code's (exit code, stdout, stderr)."""

    if row == CC:
        done = fire(row, digest, root, **options)
        assert isinstance(done, subprocess.CompletedProcess)
        return [(done.returncode, done.stdout, done.stderr)]
    since = finish_helpers.now()
    printed = [stop_json(row, digest, root, **options)]
    if finish_helpers.settle(git_root(root), since) is not None:
        since = finish_helpers.now()
        printed.append(stop_json(row, digest, root, **options))
        finish_helpers.settle(git_root(root), since)
    return printed


def test_no_path_but_a_hold_writes_to_the_model(tmp_path: Path) -> None:
    """Breaks if any verdict but a hold reaches the model: a `decision`, a `reason` or context
    from the codex stop, anything on claude-code's streams, or text from either turn-start entry
    but the claude-code person's `systemMessage`."""

    held: list[bool] = []

    def judge(row: str, printed: list[Any], holds: bool) -> None:
        for item in printed:
            if row == CC:
                code, out, err = item
                assert out == b"", out
                assert (code == 2) == bool(err), item
                assert code in (0, 2), item
                held.append(code == 2)
            else:
                assert set(item) <= {"decision", "reason", "systemMessage"}, item
                assert ("decision" in item) == ("reason" in item), item
                assert "decision" not in item or "systemMessage" not in item, item
                held.append("decision" in item)
        assert any(held[-len(printed) :]) == holds, (row, printed)

    for row in ROWS:
        place = tmp_path / row
        place.mkdir()
        root, digest = target(place / "pass", ["true"])
        judge(row, outputs(row, digest, root), False)
        judge(row, outputs(row, digest, root), False)  # the tree already checked
        root, digest = target(place / "hold", ["echo boom; exit 1"])
        judge(row, outputs(row, digest, root), True)
        guard = INPUT[row] | {"cwd": str(root), "stop_hook_active": True}
        write(root / "src.txt", "two\n")
        judge(row, outputs(row, digest, root, stdin=guard, cwd=root), False)
        root, digest = target(place / "known", ["echo old; exit 1"])
        finish_check.measure(root, ["echo old; exit 1"], 600)
        write(root / "src.txt", "two\n")
        judge(row, outputs(row, digest, root), False)
        root, digest = target(place / "missing", ["no-such-tool-here-zz"])
        judge(row, outputs(row, digest, root), False)
        root, digest = target(place / "changed", ["echo again >> grows.txt; exit 1"])
        judge(row, outputs(row, digest, root), False)
        root, _ = target(place / "digest", ["true"])
        judge(row, outputs(row, finish_check.done_digest(["make"]), root), False)
        empty = place / "empty"
        empty.mkdir()
        judge(row, outputs(row, digest, empty, cwd=empty), False)
        root, digest = target(place / "unchanged", ["echo boom; exit 1"])
        assert turn(row, digest, root) == ""
        judge(row, outputs(row, digest, root), False)
        root, digest = target(place / "limit", ["sleep 5"])
        judge(row, outputs(row, digest, root, timeout=finish_check.MARGIN_SECONDS + 1), False)
        if row == CC:
            root, digest = target(place / "paused", ["echo boom; exit 1"])
            judge(row, outputs(row, digest, root, stdin=paused(root, WAITING[0])), False)
        # The turn-start entry: codex prints nothing; claude-code only the person's notices.
        printed = mark(row, digest, root)
        assert printed.returncode == 0 and printed.stderr == b""
        if row == "codex":
            assert printed.stdout == b""
        elif printed.stdout:
            assert list(json.loads(printed.stdout)) == ["systemMessage"]


def test_each_notice_is_told_once_for_a_session_tree_and_kind(tmp_path: Path) -> None:
    """Breaks if a notice is repeated at every stop, or if one notice hides another of a
    different kind on the same tree (a notice that Done is still running hid the verdict that
    followed), or one for another session."""

    started, go, gate = gated(tmp_path)
    root, digest = target(tmp_path / "t", [gate])
    since = finish_helpers.now()
    assert stop_json("codex", digest, root) == {}
    wait_for(started)

    running = stop_json("codex", digest, root)["systemMessage"]
    assert "still running on this tree since" in running
    assert stop_json("codex", digest, root) == {}
    write(go, "")
    finish_helpers.wait_for_run(root, since)
    assert stop_json("codex", digest, root)["systemMessage"].startswith("finish-check PASS: ")
    assert stop_json("codex", digest, root) == {}
    again = stop_json("codex", digest, root, stdin=other_session("codex", root))
    assert again["systemMessage"].startswith("finish-check PASS: ")


def files_under(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_status_prints_the_run_and_the_record_of_the_current_tree_and_writes_nothing(
    tmp_path: Path,
) -> None:
    """Breaks if `--status` writes anything, the Git directory included, or leaves out how the
    run ended or the record of the tree the person stands on."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    assert hook(CC, digest, root)[0] == 2
    before = files_under(root)

    shown = finish_helpers.status(root)

    assert files_under(root) == before
    assert "ended" in shown and "fail" in shown.lower()
    assert "this tree" in shown and "```output\nboom\n```" in shown


def test_the_claude_code_turn_start_entry_prints_each_untold_notice_once_as_a_system_message(
    tmp_path: Path,
) -> None:
    """Breaks if the claude-code person never hears a verdict that did not hold (an async hook
    can show nothing else), hears it at every prompt, or the prompt hook prints anything the
    model would read."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    guarded = {**INPUT[CC], "cwd": str(root), "stop_hook_active": True}
    assert hook(CC, digest, root, stdin=guarded) == (0, {})

    first = turn(CC, digest, root)
    assert "finish-check FAIL" in first and "boom" in first
    assert turn(CC, digest, root) == ""
    other = {"session_id": "another", "hook_event_name": "UserPromptSubmit", "cwd": str(root)}
    assert "finish-check FAIL" in turn(CC, digest, root, stdin=other)


def test_the_codex_turn_start_entry_prints_nothing(tmp_path: Path) -> None:
    """Breaks if the codex prompt hook prints anything: a prompt hook's plain text is added to
    the model's context, and codex tells the person at the stop."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    guarded = {**INPUT["codex"], "cwd": str(root / "deeper"), "stop_hook_active": True}
    (root / "deeper").mkdir()
    since = finish_helpers.now()
    assert stop_json("codex", digest, root, stdin=guarded) == {}
    finish_helpers.wait_for_run(root, since)

    done = mark("codex", digest, root)

    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")


@pytest.mark.parametrize("row", ROWS)
def test_a_failure_held_once_goes_to_the_person_on_any_later_tree_in_the_session(
    tmp_path: Path, row: str
) -> None:
    """Breaks if the same failure holds the model again in the session on a new tree: the same
    environment crash was held once on each new tree."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    assert hook(row, digest, root)[1]["decision"] == "block"

    for text in ("two\n", "three\n"):
        write(root / "src.txt", text)
        message = person(row, root, hook(row, digest, root)[1])
        assert "boom" in message and "held once already in this session" in message


def test_a_new_failure_id_exit_code_or_assertion_message_holds_in_the_same_session(
    tmp_path: Path,
) -> None:
    """Breaks if a different failure of the same command passes for one already held: a new
    exit code, a new failure id, or a new assertion message in the same test."""

    out, code = tmp_path / "out", tmp_path / "code"
    write(out, "FAILED tests/a.py::t - assert x == y\n")
    write(code, "1")
    root, digest = target(tmp_path / "t", [f'cat {q(out)}; exit "$(cat {q(code)})"'])
    assert hook("codex", digest, root)[1]["decision"] == "block"

    changes = [
        (code, "2"),
        (out, "FAILED tests/a.py::t - assert x == y\nFAILED tests/b.py::u - assert u\n"),
        (out, "FAILED tests/a.py::t - assert z == y\n"),
    ]
    for number, (path, text) in enumerate(changes):
        write(path, text)
        write(root / "src.txt", f"{number} {text}")
        assert hook("codex", digest, root)[1]["decision"] == "block", text


def test_another_session_holds_the_same_failure_once(tmp_path: Path) -> None:
    """Breaks if one session's hold silences the same failure in a new session, which may cause
    it anew, or if that session is held for it twice."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    assert hook("codex", digest, root)[1]["decision"] == "block"
    another = other_session("codex", root)

    write(root / "src.txt", "two\n")
    assert hook("codex", digest, root, stdin=another)[1]["decision"] == "block"
    write(root / "src.txt", "three\n")
    assert "decision" not in hook("codex", digest, root, stdin=another)[1]


def failed(output: str, command: str = "make test", code: int = 2) -> finish_check.Result:
    data = output.encode()
    ids = finish_check.failure_ids(data)
    return finish_check.Result(command, finish_check.FAIL, 1.0, "exit", data, code=code, ids=ids)


def test_the_signature_reads_digits_hex_runs_the_target_path_temp_folder_and_line_order_away(
    tmp_path: Path,
) -> None:
    """Breaks if a timing, a process id, an object id, a scratch path, the checkout's own place
    or a parallel runner's order makes the same failure a new one; a new message is new."""

    first, second = tmp_path / "one", tmp_path / "two"
    temporary = Path(tempfile.gettempdir())

    def lines(root: Path, number: int, scratch: str, order: int) -> str:
        found = [
            f"error in {root}/src/a.py line {number}",
            f"{temporary}/{scratch}/x.txt was not written",
            f"object at 0x{number:012x}",
            f"took {number}.{number} s",
            "the last line",
        ]
        return "\n".join(found if order else list(reversed(found))) + "\n"

    one = finish_check.signature(failed(lines(first, 12, "tmp1234", 1)), first)
    two = finish_check.signature(failed(lines(second, 97, "tmp9876", 0)), second)
    assert one == two
    changed = lines(first, 12, "tmp1234", 1).replace("the last line", "another line")
    assert finish_check.signature(failed(changed), first) != one


def test_with_failure_ids_a_new_warning_line_does_not_change_the_signature(
    tmp_path: Path,
) -> None:
    """Breaks if output beside the runner's failure lines (a warning, a longer traceback)
    splits one failure into two holds, or if a new message on the failure line does not."""

    base = "FAILED tests/a.py::t - assert x == y\n1 failed in 0.12s\n"
    noisy = "DeprecationWarning: old\n" + "  frame\n" * 30 + base
    assert finish_check.signature(failed(base), tmp_path) == finish_check.signature(
        failed(noisy), tmp_path
    )
    other = base.replace("x == y", "x == z")
    assert finish_check.signature(failed(other), tmp_path) != finish_check.signature(
        failed(base), tmp_path
    )


@pytest.mark.parametrize("row", ROWS)
def test_a_failure_the_turn_began_with_is_not_held_when_a_run_delivers_it(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a failure the session was already held for, and that the tree the turn began
    with had, holds the turn again."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    assert hook(row, digest, root)[1]["decision"] == "block"
    turn(row, digest, root)
    write(root / "src.txt", "two\n")

    message = person(row, root, hook(row, digest, root)[1])

    assert "known before this turn" in message


def grow_record(row: str, root: Path, digest: str, grow: Path, stdin: Any = None) -> None:
    """A run whose Done fails and then writes into the tree, so that its record is one of a
    tree that changed; the flag and the file it wrote are then taken away."""

    write(grow, "")
    if row == "codex":
        since = finish_helpers.now()
        assert stop_json(row, digest, root, stdin=stdin) == {}
        finish_helpers.wait_for_run(root, since)
    else:
        assert hook(row, digest, root, stdin=stdin) == (0, {})
    record = finish_check.last_checked(root)
    assert record is not None and record.kind == finish_check.CHANGED
    grow.unlink()
    (root / "grows.txt").unlink()


def grower(tmp_path: Path) -> tuple[Path, Path, str]:
    grow = tmp_path / "grow"
    root, digest = target(
        tmp_path / "t", [f"echo boom; if [ -e {q(grow)} ]; then echo x >> grows.txt; fi; exit 1"]
    )
    return root, grow, digest


@pytest.mark.parametrize("row", ROWS)
def test_another_sessions_changed_tree_record_is_a_baseline_and_its_failure_is_told(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a failure another session's run saw on the tree this turn began with, while
    that tree was changing, holds this session's turn."""

    root, grow, digest = grower(tmp_path)
    grow_record(row, root, digest, grow, stdin=other_session(row, root))
    turn(row, digest, root)
    write(root / "src.txt", "two\n")

    _, verdict = hook(row, digest, root)

    assert "decision" not in verdict
    assert "known before this turn" in person(row, root, verdict)


@pytest.mark.parametrize("row", ROWS)
def test_this_sessions_undelivered_failure_on_the_start_tree_holds_when_found_again(
    tmp_path: Path, row: str
) -> None:
    """Breaks if the session's own failure, which the model never heard of, reads as one the
    turn began with and goes unheld, or holds before a run finds it again."""

    root, grow, digest = grower(tmp_path)
    grow_record(row, root, digest, grow)
    first = finish_check.last_checked(root)
    assert first is not None
    turn(row, digest, root)
    write(root / "src.txt", "two\n")

    _, verdict = hook(row, digest, root)

    assert verdict["decision"] == "block"
    assert verdict["reason"].startswith(
        f"finish-check FAIL: Done failed on the tree this turn began with, at {clock(first.time)}, "
        "and still fails now"
    )


@pytest.mark.parametrize("row", ROWS)
def test_a_delivered_signature_on_the_start_tree_is_told_and_not_held(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a failure already held in the session, seen again on the tree a later turn
    began with while that tree was changing, holds again."""

    root, grow, digest = grower(tmp_path)
    assert hook(row, digest, root)[1]["decision"] == "block"
    write(root / "src.txt", "two\n")
    grow_record(row, root, digest, grow)
    turn(row, digest, root)
    write(root / "src.txt", "three\n")

    _, verdict = hook(row, digest, root)

    assert "decision" not in verdict
    assert "known before this turn" in person(row, root, verdict)


def test_an_undelivered_signature_carries_forward_when_the_person_types_first_again(
    tmp_path: Path,
) -> None:
    """Breaks if a failure is lost because the person typed before each run ended: the first
    run that confirms it with no prompt in between delivers it, naming when it was first
    found."""

    started, go, gate = gated(tmp_path)
    root, digest = target(tmp_path / "t", [f"{gate}; echo boom; exit 1"])
    turn(CC, digest, root)
    write(root / "src.txt", "two\n")
    deferred(tmp_path, root, digest, started, go)
    first = finish_check.last_checked(root)
    assert first is not None
    go.unlink()
    write(root / "src.txt", "three\n")
    deferred(tmp_path, root, digest, started, go)
    write(root / "src.txt", "four\n")

    code, verdict = hook(CC, digest, root)

    assert code == 2
    assert f"at {clock(first.time)}, and still fails now" in verdict["reason"].splitlines()[0]


def test_a_tree_changed_with_no_session_moving_it_records_the_cause(tmp_path: Path) -> None:
    """Breaks if a Done that writes into the tree, and so is never checked, goes unnamed: no
    prompt was written while it ran, so nothing in a session moved the tree."""

    root, digest = target(tmp_path / "t", ["echo again >> grows.txt"])
    start = finish_check.tree_digest(root, digest)

    assert hook(CC, digest, root) == (0, {})

    record = finish_check.checked_for(root, start)
    assert record is not None and record.cause == finish_check.OUTSIDE
    assert (
        "Done, or something outside the session, writes into the tree; have Done write only what "
        "Git ignores"
    ) in finish_helpers.status(root)


@pytest.mark.parametrize("row", ROWS)
def test_without_a_baseline_a_failure_holds_once_then_goes_to_the_person(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a failure with no record of the tree the turn began with never holds (a first
    install, a fresh clone), holds without saying it may predate the turn, or holds twice."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])

    _, verdict = hook(row, digest, root)
    head = verdict["reason"].splitlines()[0]
    assert "no record of the tree this turn began with was found" in head

    write(root / "src.txt", "two\n")
    assert "boom" in person(row, root, hook(row, digest, root)[1])


def test_a_run_on_a_changed_tree_supersedes_the_running_run_and_its_commands_grandchild_included(
    tmp_path: Path,
) -> None:
    """Breaks if a run on a tree that is gone keeps Done running beside the new one, or leaves
    a process its command started."""

    holder = (
        "import os, subprocess, sys\n"
        "if os.path.exists(sys.argv[1]):\n"
        "    sys.exit(0)\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "open(sys.argv[1], 'w').write(str(child.pid))\n"
        "child.wait()\n"
    )
    write(tmp_path / "holder.py", holder)
    pid_file = tmp_path / "child.pid"
    line = f"{q(sys.executable)} {q(tmp_path / 'holder.py')} {q(pid_file)}"
    root, digest = target(tmp_path / "t", [line])
    first = fire(CC, digest, root, background=True)
    wait_for(pid_file)
    time.sleep(0.2)
    child = int(pid_file.read_text(encoding="utf-8"))
    write(root / "src.txt", "two\n")

    second = fire(CC, digest, root, background=True)

    finished(first, 60)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and running(child):
        time.sleep(0.1)
    assert not running(child)
    assert finished(second) == (0, b"", b"")


def test_a_run_on_the_running_tree_leaves_the_run(tmp_path: Path) -> None:
    """Breaks if a stop on the tree a run is checking starts Done again or ends that run."""

    started, go, gate = gated(tmp_path)
    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; {gate}"])
    since = finish_helpers.now()
    assert stop_json("codex", digest, root) == {}
    record = finish_helpers.wait_for_run(root, since, ended=False)
    wait_for(started)

    assert "decision" not in stop_json("codex", digest, root)

    time.sleep(1)
    now = finish_helpers.run_record(root)
    assert now is not None and now["pid"] == record["pid"] and counted(count) == 1
    write(go, "")
    finish_helpers.wait_for_run(root, since)
    assert counted(count) == 1


def test_a_killed_run_leaves_the_lock_free_for_the_next_run(tmp_path: Path) -> None:
    """Breaks if a run killed from outside, which runs none of its code, leaves the lock held,
    so that no later run starts."""

    started, go, gate = gated(tmp_path)
    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}; {gate}"])
    first = fire(CC, digest, root, background=True)
    wait_for(started)
    first.kill()
    first.communicate(timeout=30)
    write(go, "")
    write(root / "src.txt", "two\n")
    begun = time.monotonic()

    assert hook(CC, digest, root) == (0, {})

    assert time.monotonic() - begun < 20 and counted(count) == 2


@posix_only
def test_a_lock_still_held_after_30_s_starts_nothing_sends_nothing_more_and_tells_the_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a run whose holder will not stop sends it more than the one SIGTERM (a
    `SIGKILL` by a recorded id can reach a process that is not the run), starts Done beside it,
    or says nothing. POSIX: on Windows the holder is ended with TerminateProcess, which a process
    cannot refuse. The 30 s wait is cut to 2 here."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {q(count)}"])
    lock = root / ".git" / finish_check.RUN_LOCK
    record = root / ".git" / finish_check.RUN
    terms = tmp_path / "terms"
    holder = (
        "import fcntl, json, os, signal, sys, time\n"
        "from datetime import datetime, timezone\n"
        "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)\n"
        "fcntl.flock(fd, fcntl.LOCK_EX)\n"
        "signal.signal(signal.SIGTERM, lambda *a: open(sys.argv[3], 'a').write('term\\n'))\n"
        "record = {'pid': os.getpid(), 'tree': '0' * 64, 'head': '', 'session': 'x',\n"
        "          'started': datetime.now(timezone.utc).isoformat(), 'mark': None,\n"
        "          'done': sys.argv[4], 'timeout': 600}\n"
        "open(sys.argv[2], 'w').write(json.dumps(record))\n"
        "print('ready', flush=True)\n"
        "time.sleep(120)\n"
    )
    write(tmp_path / "holder.py", holder)
    process = subprocess.Popen(
        [sys.executable, str(tmp_path / "holder.py"), str(lock), str(record), str(terms), digest],
        stdout=subprocess.PIPE,
    )
    try:
        assert process.stdout is not None and process.stdout.readline() == b"ready\n"
        monkeypatch.setattr(finish_check, "SUPERSEDE_SECONDS", 2)
        given = json.dumps({**INPUT[CC], "cwd": str(root), "transcript_path": None}).encode()
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(given)))
        monkeypatch.chdir(root)

        assert finish_check.main(["--constant-time", "--harness", CC, "--done", digest]) == 0

        assert counted(count) == 0
        assert terms.read_text(encoding="utf-8") == "term\n"
        assert "did not stop within" in finish_helpers.status(root)
        assert "did not stop within" in turn(CC, digest, root)
    finally:
        process.kill()
        process.communicate(timeout=30)


def test_the_holder_opens_the_lock_file_once_and_a_done_command_does_not_inherit_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the run opens the lock file a second time (a second descriptor's close can
    release a record lock while the run lives), or if a Done command inherits it and keeps the
    lock alive after the run."""

    seen = tmp_path / "seen"
    probe = (
        "import os, sys\n"
        "lock = os.stat(sys.argv[1])\n"
        "found = 'clean'\n"
        "for fd in range(3, 1024):\n"
        "    try:\n"
        "        held = os.fstat(fd)\n"
        "    except OSError:\n"
        "        continue\n"
        "    if (held.st_dev, held.st_ino) == (lock.st_dev, lock.st_ino):\n"
        "        found = 'inherited'\n"
        "open(sys.argv[2], 'w').write(found)\n"
    )
    write(tmp_path / "probe.py", probe)
    root, _ = target(tmp_path / "t", ["true"])
    lock = root / ".git" / finish_check.RUN_LOCK
    line = f"{q(sys.executable)} {q(tmp_path / 'probe.py')} {q(lock)} {q(seen)}"
    manifest = json.loads((root / finish_check.MANIFEST).read_text(encoding="utf-8"))
    manifest["artifacts"][0]["done"] = [line]
    write(root / finish_check.MANIFEST, json.dumps(manifest))
    digest = finish_check.done_digest([line])
    opened: list[str] = []
    real = os.open

    def counting(path: Any, *arguments: Any, **options: Any) -> int:
        if str(path).endswith(finish_check.RUN_LOCK):
            opened.append(str(path))
        return real(path, *arguments, **options)

    monkeypatch.setattr(finish_check.os, "open", counting)
    given = json.dumps({**INPUT[CC], "cwd": str(root), "transcript_path": None}).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(given)))
    monkeypatch.chdir(root)

    assert finish_check.main(["--constant-time", "--harness", CC, "--done", digest]) == 0

    assert len(opened) == 1 and seen.read_text(encoding="utf-8") == "clean"


def test_a_codex_stop_whose_tree_read_passes_its_deadline_still_starts_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a checkout too large to read within the stop's 20 seconds is never checked:
    the stop tells the person once and starts the run, which reads it with its own budget."""

    root, digest = target(tmp_path / "t", ["true"])
    started: list[list[str]] = []
    printed = Kept()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(printed, encoding="utf-8"))
    monkeypatch.setattr(
        finish_check.programs, "start_detached", lambda argv, **options: started.append(argv)
    )
    monkeypatch.setattr(finish_check, "STOP_READ_SECONDS", -1)
    given = json.dumps({**INPUT["codex"], "cwd": str(root), "transcript_path": None}).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(given)))
    monkeypatch.chdir(root)

    assert finish_check.main(["--constant-time", "--harness", "codex", "--done", digest]) == 0

    verdict = json.loads(printed.getvalue())
    assert list(verdict) == ["systemMessage"]
    assert verdict["systemMessage"].startswith("finish-check UNVERIFIED: ")
    assert "could not be read within" in verdict["systemMessage"]
    assert len(started) == 1


def test_a_record_cut_short_reads_as_absent_and_a_run_record_cut_short_as_a_dead_run(
    tmp_path: Path,
) -> None:
    """Breaks if a record a crash cut short wedges the check: a checked-tree record that cannot
    be parsed is no record, and a run record that cannot be parsed is a run that did not
    finish, which the person is told."""

    root, digest = target(tmp_path / "t", ["true"])
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"]
    run_path = root / ".git" / finish_check.RUN
    text = run_path.read_text(encoding="utf-8")
    write(run_path, text[: len(text) // 2])

    told = stop_json("codex", digest, root)["systemMessage"]
    assert "did not finish" in told

    state = root / ".git" / finish_check.STATE
    text = state.read_text(encoding="utf-8")
    write(state, text[: len(text) // 2])
    assert finish_check.last_checked(root) is None
    hook("codex", digest, root)  # the tree has no record: a run starts and checks it again
    record = finish_check.last_checked(root)
    assert record is not None and record.verdict == finish_check.PASS


def test_a_run_record_without_ended_whose_process_is_gone_reads_as_a_dead_run(
    tmp_path: Path,
) -> None:
    """Breaks if a run that was killed (at a session's teardown, or with no `ended` written)
    reads as running, so that no run starts, or passes unnamed."""

    root, digest = target(tmp_path / "t", ["true"])
    gone = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, check=True
    )
    record = {
        "pid": int(gone.stdout),
        "tree": finish_check.tree_digest(root, digest),
        "head": "",
        "started": finish_helpers.now().isoformat(),
        "session": "s",
        "mark": None,
        "done": digest,
        "timeout": 600,
    }
    write(root / ".git" / finish_check.RUN, json.dumps(record))
    since = finish_helpers.now()

    told = stop_json("codex", digest, root)["systemMessage"]

    assert "did not finish" in told
    finish_helpers.wait_for_run(root, since)


def hold_lock(path: Path) -> int:
    """Take the run lock as a run does, from this process."""

    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return descriptor


def test_a_run_record_older_than_its_limit_plus_60_s_reads_as_a_dead_run(tmp_path: Path) -> None:
    """Breaks if a run record whose start is past its limit plus 60 seconds reads as running
    because its id now names some other live process."""

    root, digest = target(tmp_path / "t", ["true"])
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"]
    old = finish_helpers.now() - timedelta(seconds=600 + 61)
    record = {
        "pid": os.getpid(),
        "tree": finish_check.tree_digest(root, digest),
        "head": "",
        "started": old.isoformat(),
        "session": "s",
        "mark": None,
        "done": digest,
        "timeout": 600,
    }
    write(root / ".git" / finish_check.RUN, json.dumps(record))
    descriptor = hold_lock(root / ".git" / finish_check.RUN_LOCK)
    try:
        told = stop_json("codex", digest, root)["systemMessage"]
    finally:
        os.close(descriptor)

    assert "did not finish" in told


@pytest.mark.parametrize("row", ROWS)
def test_the_run_writes_nothing_outside_the_git_directory(tmp_path: Path, row: str) -> None:
    """Breaks if the run leaves a log, a lock or a record in the working tree, which would change
    the tree it checks and land in a commit."""

    root, digest = target(tmp_path / "t", ["true"])
    if row == "codex":
        (root / "deeper").mkdir()
    write(root / "src.txt", "two\n")

    def outside() -> tuple[dict[str, tuple[bytes, int]], str]:
        files = {k: v for k, v in files_under(root).items() if not k.startswith(".git/")}
        listed = subprocess.run(
            [GIT, "-C", str(root), "status", "--porcelain", "--ignored"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return files, listed

    before = outside()

    hook(row, digest, root)

    assert outside() == before


# --- The constant-time stop: what the built change's review found -----------------------


def test_a_follower_whose_budget_ended_first_does_not_wake_the_model_a_second_time(
    tmp_path: Path,
) -> None:
    """Breaks if a follower that waited past its own budget reads the held list with that spent
    budget, finds it empty and sends the holder's hold again."""

    started, go, gate = gated(tmp_path)
    root, digest = target(tmp_path / "t", [f"{gate}; echo boom; exit 1"])
    holder = fire(CC, digest, root, timeout=600, background=True)
    wait_for(started)
    follower = fire(CC, digest, root, timeout=31, background=True)
    # The follower's budget for its records ends 16 s after it starts; the holder ends after.
    time.sleep(finish_check.REMEMBER_SECONDS + 3)
    assert follower.poll() is None
    write(go, "")

    code, out, err = finished(holder)
    assert (code, out) == (2, b"") and "boom" in err.decode()
    assert finished(follower) == (0, b"", b"")


@pytest.mark.parametrize("row", ROWS)
def test_a_failure_whose_held_list_cannot_be_written_goes_to_the_person_not_the_model(
    tmp_path: Path, row: str
) -> None:
    """Breaks if a hold goes out while the held list cannot be written, so that the same failure
    would reach the model at every turn end, or if the person is not told of it."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    (root / ".git" / finish_check.HELD).mkdir()

    if row == CC:
        assert hook(row, digest, root) == (0, {})
        message = turn(row, digest, root)
        assert finish_check.UNHELD_WHY in message and "boom" in message
        assert finish_check.UNHELD_WHY in finish_helpers.status(root)
    else:
        _, verdict = hook(row, digest, root)
        assert list(verdict) == ["systemMessage"], verdict
        assert finish_check.UNHELD_WHY in verdict["systemMessage"]


@posix_only
def test_a_run_lock_that_cannot_be_opened_is_told_to_the_person(tmp_path: Path) -> None:
    """Breaks if a lock file the run cannot open leaves no record and no notice."""

    if os.geteuid() == 0:
        pytest.skip("root opens a file of mode 0")
    root, digest = target(tmp_path / "t", ["true"])
    lock = root / ".git" / finish_check.RUN_LOCK
    write(lock, "")
    lock.chmod(0)
    try:
        assert hook(CC, digest, root) == (0, {})
        shown = finish_helpers.status(root)
        message = turn(CC, digest, root)
    finally:
        lock.chmod(0o600)
    assert "cannot be opened" in shown
    assert "ended without a verdict" in message and "cannot be opened" in message


def test_a_failure_an_unchanged_turn_delivered_is_not_told_as_kept_from_the_agent(
    tmp_path: Path,
) -> None:
    """Breaks if, after a stop that ran nothing delivered the tree's failure to the model, the
    next prompt tells the person it was told to them and not to the agent."""

    root, digest = target(tmp_path / "t", ["echo boom; exit 1"])
    assert hook(CC, digest, root, stdin=paused(root, WAITING[0])) == (0, {})
    turn(CC, digest, root)

    code, verdict = hook(CC, digest, root)
    assert code == 2 and "boom" in verdict["reason"]

    assert "not the agent" not in turn(CC, digest, root)


def test_the_turn_start_entry_keeps_to_one_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the turn-start entry gives its notices a fresh budget after the one it spent
    reading the tree, which together could pass the harness's timeout for the entry."""

    seen: dict[str, float | None] = {}

    def begin(digest: str, payload: Any, cwd: Path, session: str, deadline: Any = None) -> Any:
        seen["begin"] = deadline
        return tmp_path, "0" * 40

    def notices(target: Path, session: str, tree: Any, digest: str, deadline: Any = None) -> Any:
        seen["notices"] = deadline
        return []

    monkeypatch.setattr(finish_check, "begin_turn", begin)
    monkeypatch.setattr(finish_check, "turn_notices", notices)
    payload = json.dumps({"session_id": "s", "hook_event_name": "UserPromptSubmit"}).encode()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload)))
    words = ["--mark", "--harness", CC, "--done", "0" * 64]

    assert finish_check.main(words) == 0
    assert seen["begin"] is not None and seen["notices"] == seen["begin"]


def test_a_codex_stop_that_raises_prints_nothing_for_the_model_and_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if an unexpected error in the codex stop ends the hook with a traceback and exit 1,
    which codex shows as a hook error at the turn end."""

    def broken(*_: Any) -> Any:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(finish_check, "stop", broken)
    monkeypatch.setattr(finish_check, "_close_stdout", lambda: None)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"{}")))

    code = finish_check.main(["--harness", "codex", "--done", "0" * 64])

    assert (code, capsys.readouterr().out) == (0, "{}\n")


def test_the_told_file_keeps_only_the_current_sessions_entries(tmp_path: Path) -> None:
    """Breaks if the file of notices told grows with every session that ever ran."""

    root, _digest = target(tmp_path / "t", ["true"])
    path = root / ".git" / finish_check.TOLD
    old = [["old-session", "a" * 40, "pass"], ["s", "b" * 40, "pass"]]
    write(path, json.dumps({"told": old}) + "\n")

    told = finish_check.tell(root, "s", [finish_check.Notice("c" * 40, "fail", "text")])

    assert told == ["text"]
    kept = json.loads(path.read_text(encoding="utf-8"))["told"]
    assert sorted(kept) == [["s", "b" * 40, "pass"], ["s", "c" * 40, "fail"]]


def test_the_detached_runs_command_line_names_no_transcript(tmp_path: Path) -> None:
    """Breaks if the codex run's command line, which `ps` shows to every account, carries the
    transcript path."""

    entry = finish_check.Entry("codex", {"guard": "stop_hook_active"}, "0" * 64, 600)
    payload = {"session_id": "s", "transcript_path": "/secret/transcript.jsonl", "cwd": "x"}

    argv = finish_check._run_argv(entry, payload, tmp_path, None)

    assert "/secret/transcript.jsonl" not in " ".join(argv)
    assert json.loads(argv[-1])["session_id"] == "s"
