"""`outcomebound finish-check`, the verb a harness's stop hook runs.

Each test runs the launcher in a real subprocess on a scratch Git repository under `tmp_path`,
with the hook's input on stdin in the row's own shape, and reads the JSON the harness would read.
Each names the break it catches.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import finish_check

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "scripts" / "outcomebound"
GIT = shutil.which("git") or "git"
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
    (path / ".outcomebound/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "src.txt").write_text("one\n", encoding="utf-8")
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    subprocess.run([GIT, "-C", str(path), "add", "."], check=True)
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([GIT, "-C", str(path), *identity, "commit", "-qm", "init"], check=True)
    return path, finish_check.done_digest(done)


def hook(
    row: str,
    digest: str,
    root: Path,
    stdin: bytes | dict[str, Any] | None = None,
    cwd: Path | None = None,
    timeout: int | None = None,
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
    data = stdin if isinstance(stdin, bytes) else json.dumps(stdin).encode()
    words = [str(LAUNCHER), "finish-check", "--harness", row, "--done", digest]
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
    root, digest = target(tmp_path / "t", [f"echo run >> {count}"])

    def runs() -> int:
        return len(count.read_text(encoding="utf-8").splitlines()) if count.exists() else 0

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 1
    assert hook("codex", digest, root)[1] == {} and runs() == 1
    (root / "src.txt").write_text("two\n", encoding="utf-8")
    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"] and runs() == 2
    (root / "new.txt").write_text("new\n", encoding="utf-8")
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
    root, digest = target(tmp_path / "t", [f"echo run >> {count}; echo boom; exit 1"])

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
    (root / "src.txt").write_text("two\n", encoding="utf-8")
    assert hook("codex", digest, root)[1]["decision"] == "block" and runs() == 2


def test_an_unchanged_tree_that_timed_out_runs_again_only_under_a_longer_timeout(
    tmp_path: Path,
) -> None:
    """Breaks if a timed-out tree is run again, the limit spent, at every turn end, or if
    raising the timeout cannot get the same tree checked."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"echo run >> {count}; sleep 3"])
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
    ("line", "code"), [("no-such-tool-here --check", 127), ("./not-executable", 126)]
)
def test_a_command_the_hooks_environment_cannot_run_is_unverified_and_holds_nothing(
    tmp_path: Path, line: str, code: int
) -> None:
    """Breaks if a tool missing from the hook's PATH, or a file that cannot be executed, holds
    the finish as a failure the agent's change caused."""

    root, digest = target(tmp_path / "t", [line])
    (root / "not-executable").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    _, verdict = hook("codex", digest, root)

    assert list(verdict) == ["systemMessage"]
    message = verdict["systemMessage"]
    assert message.startswith(
        f"finish-check UNVERIFIED: `{line}` could not run in the hook's environment"
    )
    assert f"UNVERIFIED {line}: exit {code} after " in message


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
    root, digest = target(tmp_path / "t", [f"echo run >> {count}"])
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


def test_a_script_that_loses_its_execute_bit_is_checked_again(tmp_path: Path) -> None:
    """Breaks if a pass cached for an untracked script survives the script becoming unrunnable."""

    root, digest = target(tmp_path / "t", ["./check.sh"])
    script = root / "check.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)

    assert "PASS" in hook("codex", digest, root)[1]["systemMessage"]
    script.chmod(0o644)
    verdict = hook("codex", digest, root)[1]
    assert list(verdict) == ["systemMessage"]
    assert "UNVERIFIED ./check.sh: exit 126" in verdict["systemMessage"]


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

    printer = "python3 -c 'print(chr(96) * 10000)'; echo last; exit 1"
    root, digest = target(tmp_path / "t", [printer])

    reason = hook("codex", digest, root)[1]["reason"]
    assert len(reason) < finish_check.REPORT_CHARACTERS
    assert "[10000 backticks]" in reason and reason.endswith("last\n```")


def test_a_pass_too_near_the_limit_is_reported_and_not_remembered(tmp_path: Path) -> None:
    """Breaks if reading the tree again and remembering it can run past their own deadline:
    with the time left for them already spent, the pass is reported and the next turn end runs
    again."""

    count = tmp_path / "count"
    root, digest = target(tmp_path / "t", [f"sleep 1; echo run >> {count}"])
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
    (root / "new.txt").write_text("new\n", encoding="utf-8")
    assert finish_check.tree_digest(root, digest, time.monotonic() - 1) is None
    assert finish_check.tree_digest(root, digest) is not None


def test_a_command_past_the_limit_is_stopped_with_its_group_and_holds_nothing(
    tmp_path: Path,
) -> None:
    """Breaks if a slow check is left for the harness to cut off, if the commands do not stop
    the margin before the entry's own timeout, if a process it started keeps running, or if the
    report offers shortening Done before a longer limit: the entry's timeout is one second past
    the margin."""

    root, digest = target(tmp_path / "t", ["sleep 60 & echo $! > child.pid; wait"])
    timeout = finish_check.MARGIN_SECONDS + 1
    started = time.monotonic()

    _, verdict = hook("codex", digest, root, cwd=root, timeout=timeout)

    assert time.monotonic() - started < 30
    assert list(verdict) == ["systemMessage"]
    message = verdict["systemMessage"]
    assert message.startswith(
        f"finish-check UNVERIFIED: `sleep 60 & echo $! > child.pid; wait` did not finish within "
        f"1 s, {finish_check.MARGIN_SECONDS} s before the hook's {timeout} s timeout"
    )
    assert f"--finish-timeout <seconds>`, for example {2 * timeout}" in message
    assert message.index("--finish-timeout") < message.index("--no-finish-check")
    assert "stopped at the time limit after 1 s" in message
    child = int((root / "child.pid").read_text(encoding="utf-8"))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and _alive(child):
        time.sleep(0.1)
    assert not _alive(child)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


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
        [str(LAUNCHER), "finish-check", *arguments],
        input=b"{}",
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )

    assert done.returncode == 1 and done.stdout == b""
