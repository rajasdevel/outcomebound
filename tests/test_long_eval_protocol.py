"""Native accounting and protocol controls; no model or subscription calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from evals.claude_stream import reach_rows
from evals.harnesses import CallResult, Request
from evals.harnesses.claude_code import Cell
from evals.harnesses.codex import SessionMeter
from evals.long_sessions import Driver, Driving, NativeUsage, Session, SessionError, next_message
from evals.session_evidence import contamination, family_evidence
from evals.session_usage import CallUsage, codex_children
from evals.watch import watched_command
from tests.eval_helpers import RUN
from tests.portable import needs_posix_bash


def _count(total, last, out=0):
    return {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "last_token_usage": {
                    "input_tokens": last,
                    "cached_input_tokens": 0,
                    "output_tokens": out,
                    "reasoning_output_tokens": 0,
                },
                "total_token_usage": {
                    "input_tokens": total,
                    "cached_input_tokens": 0,
                    "output_tokens": out,
                    "reasoning_output_tokens": 0,
                },
            },
        },
    }


def _meta(key, parent=None):
    payload = {"id": key}
    if parent:
        payload["source"] = {"subagent": {"thread_spawn": {"parent_thread_id": parent}}}
    return {"type": "session_meta", "payload": payload}


def _rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return {"path": str(path), "copy": str(path)}


def test_literal_usage_snapshots_duplicate_stopped_restart_and_child(tmp_path):
    """Catches cumulative snapshots being added as spend and duplicate call charging."""
    usage = NativeUsage("codex")
    first = [_meta("parent"), _count(100, 100)]
    item = _rows(tmp_path / "first.jsonl", first)
    assert usage.add({"native_sessions": [item]}) == (
        1,
        {
            "input_tokens": 100,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_output_tokens": 0,
        },
    )
    # The second native copy replays the first call and repeats the second usage event.
    second = _rows(tmp_path / "second.jsonl", [*first, _count(150, 50), _count(150, 50)])
    assert usage.add({"native_sessions": [second]})[0] == 1
    assert usage.total()["input_tokens"] == 150
    assert usage.meter.reconciliation() == []
    # A stopped call has a whole usage event and an unfinished following record.
    stopped = _rows(tmp_path / "stopped.jsonl", [_meta("parent"), _count(175, 25)])
    with Path(stopped["copy"]).open("ab") as handle:
        handle.write(b'{"type":')
    assert usage.add({"native_sessions": [stopped], "stopped": "split"})[1]["input_tokens"] == 25
    fresh = _rows(tmp_path / "fresh.jsonl", [_meta("fresh"), _count(100, 100)])
    child = _rows(tmp_path / "child.jsonl", [_meta("child", "fresh"), _count(30, 30)])
    assert usage.add({"native_sessions": [fresh, child]})[0] == 2
    assert usage.total()["input_tokens"] == 305
    assert usage.add({"native_sessions": [fresh, child]})[0] == 0
    assert usage.total()["input_tokens"] == 305


def test_per_call_spend_wins_over_a_wrong_cumulative_total():
    meter = CallUsage("codex")
    meter.add([_meta("parent"), _count(100, 100), _count(999, 50)])
    assert meter.total()["input_tokens"] == 150
    (mismatch,) = meter.reconciliation()
    assert mismatch["per_call"]["input_tokens"] == 150
    assert mismatch["cumulative"]["input_tokens"] == 999


def test_claude_usage_is_per_session_and_message_including_cache_creation():
    row = {
        "type": "assistant",
        "message": {
            "id": "call-1",
            "usage": {
                "input_tokens": 10,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 10,
                "output_tokens": 5,
            },
        },
    }
    meter = CallUsage("claude-code")
    meter.add([row, row], "parent")
    meter.add([row], "child")
    meter.add([row], "fresh")
    assert len(meter.calls) == 3
    assert meter.total() == {
        "input_tokens": 300,
        "cached_input_tokens": 240,
        "cache_creation_input_tokens": 30,
        "output_tokens": 15,
        "reasoning_output_tokens": 0,
        "source": "native",
        "reasoning_in_output": True,
    }


def test_live_codex_meter_counts_child_and_only_new_resume_usage(tmp_path):
    parent = tmp_path / "rollout-parent.jsonl"
    _rows(parent, [_meta("parent"), _count(100, 100)])
    before = {parent: parent.read_bytes()}
    meter = SessionMeter(tmp_path, before, per_call=True)
    _rows(parent, [_meta("parent"), _count(100, 100), _count(150, 50)])
    _rows(tmp_path / "rollout-child.jsonl", [_meta("child", "parent"), _count(20, 20)])
    assert meter.input('{"type":"thread.started","thread_id":"parent"}\n') == 70
    assert meter.calls == 2
    assert meter.input('{"type":"thread.started","thread_id":"parent"}\n') == 70
    assert meter.calls == 2


def test_codex_child_discovery_follows_nested_parent_links_not_workspaces(tmp_path):
    _rows(tmp_path / "a.jsonl", [_meta("child", "parent")])
    _rows(tmp_path / "b.jsonl", [_meta("grandchild", "child")])
    _rows(tmp_path / "unrelated.jsonl", [_meta("unrelated", "another")])
    direct = _meta("guardian")
    direct["payload"].update(source={"subagent": {"other": "guardian"}}, parent_thread_id="parent")
    _rows(tmp_path / "c.jsonl", [direct])
    assert {(key, parent) for _, key, parent in codex_children(tmp_path, {"parent"})} == {
        ("child", "parent"),
        ("grandchild", "child"),
        ("guardian", "parent"),
    }


@pytest.mark.parametrize("mutation", ["add", "edit", "delete", "link"])
def test_claude_home_manifest_refuses_changes_between_turns(tmp_path, mutation):
    cell = Cell(tmp_path / "cell")
    cell.make()
    (cell.config / "session").write_text("run-owned", encoding="utf-8")
    cell.record()
    cell.verify()
    target = cell.config / "session"
    if mutation == "add":
        (cell.root / "foreign").mkdir()
    elif mutation == "edit":
        target.write_text("foreign", encoding="utf-8")
    elif mutation == "delete":
        target.unlink()
    else:
        target.unlink()
        target.symlink_to(tmp_path / "other")
    with pytest.raises(ValueError, match="manifest"):
        cell.verify()


def test_claude_fresh_home_stays_strict_and_resume_needs_a_manifest(tmp_path):
    cell = Cell(tmp_path / "cell")
    folders = cell.make()
    (cell.config / "foreign").write_text("foreign", encoding="utf-8")
    assert next(row for row in reach_rows(tmp_path, folders) if row[0] == "fresh-home")[1] == "FAIL"
    with pytest.raises(FileNotFoundError):
        cell.verify()
    with pytest.raises(FileExistsError):
        cell.make()


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize(
    "target",
    ["sealed/check.py", "person.json", "scripted/next.py", "sibling/file", "results/meta.json"],
)
def test_contamination_scans_all_tool_inputs_even_unknown_tools(tmp_path, harness, child, target):
    path = str(tmp_path / target)
    if harness == "codex":
        rows = [
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "unknown_read",
                    "arguments": json.dumps({"file": path}),
                },
            }
        ]
    else:
        rows = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "read",
                            "name": "Read",
                            "input": {"file_path": path},
                        }
                    ]
                },
            }
        ]
    item = {**_rows(tmp_path / "native.jsonl", rows), "child": child}
    (hit,) = contamination([item], harness, [path])
    assert hit["child"] is child and path in str(hit["input"])
    assert hit["position"] == 0


def test_contamination_resolves_relative_and_symbolic_paths(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    forbidden = tmp_path / "sealed"
    forbidden.mkdir()
    (workspace / "alias").symlink_to(forbidden, target_is_directory=True)
    item = _rows(
        tmp_path / "native.jsonl",
        [
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": {"cmd": "cat alias/check.py"},
                },
            }
        ],
    )
    assert len(contamination([item], "codex", [str(forbidden)], workspace)) == 1
    assert contamination([item], "codex", [str(tmp_path / "other")], workspace) == []


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_child_commands_files_and_unknown_tools_are_retained(tmp_path, harness):
    if harness == "codex":
        rows = [
            _meta("child", "parent"),
            _count(30, 30),
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "type": "CommandExecution",
                        "command": ["echo", "done"],
                        "cwd": str(tmp_path),
                        "status": "completed",
                        "exit_code": 0,
                        "aggregated_output": "done",
                    },
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "apply_patch",
                    "input": "*** Begin Patch\n*** Add File: result.txt\n+done\n*** End Patch",
                },
            },
        ]
    else:
        rows = [
            {
                "type": "assistant",
                "cwd": str(tmp_path),
                "message": {
                    "id": "child-call",
                    "usage": {
                        "input_tokens": 30,
                        "output_tokens": 5,
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "cmd",
                            "name": "Bash",
                            "input": {"command": "echo done"},
                        },
                        {
                            "type": "tool_use",
                            "id": "file",
                            "name": "Write",
                            "input": {"file_path": "result.txt", "content": "done"},
                        },
                    ],
                },
            },
            {
                "type": "user",
                "cwd": str(tmp_path),
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": "cmd", "content": "done"},
                        {"type": "tool_result", "tool_use_id": "file", "content": "done"},
                    ]
                },
            },
        ]
    item = {
        **_rows(tmp_path / "child.jsonl", rows),
        "child": True,
        "session_id": "child",
        "parent_id": "parent",
    }
    doc = json.dumps({"commands": [], "outputs": [], "files": [], "events": [], "stdout": ""})
    extra: dict[str, Any] = {"native_sessions": [item]}
    result = json.loads(family_evidence(doc, extra, harness, {}))
    assert result["commands"] == []
    assert result["children"][0]["commands"][0][:2] == ["echo done", "succeeded"]
    assert result["files"] == []
    assert result["children"][0]["files"][0][1] == "result.txt"
    assert result["children"][0]["parent_id"] == "parent"
    assert "--- child session child ---" in result["stdout"]
    assert extra["session_tokens"]["input_tokens"] == 30
    if harness == "codex":
        rows.append(
            {
                "type": "response_item",
                "payload": {"type": "function_call", "name": "mystery", "arguments": "{}"},
            }
        )
    else:
        rows[0]["message"]["content"].append(
            {"type": "tool_use", "id": "unknown", "name": "mystery", "input": {}}
        )
    _rows(Path(item["path"]), rows)
    result = json.loads(family_evidence(doc, extra, harness, {}))
    assert result["commands"] is result["files"] is None
    assert "mystery" in extra["unknown_tools"] and extra["decoder_verdict"] == "UNVERIFIED"


class FakeHarness:
    name = "codex"

    def __init__(self, folder, stops=(), tool=None):
        self.folder, self.stops, self.tool = folder, stops, tool
        self.requests = []
        self.rows = {}

    def call(self, message, request, cwd, roots, path, keep):
        self.requests.append(request)
        i = len(self.requests)
        key = request.resume or f"session-{i}"
        rows = self.rows.setdefault(key, [_meta(key)])
        n = len([r for r in rows if r["type"] == "event_msg"]) + 1
        rows.append(_count(n * 100, 100))
        if self.tool:
            rows.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "Read",
                        "arguments": self.tool,
                        "call_id": f"read-{i}",
                    },
                }
            )
            rows.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": f"read-{i}",
                        "output": json.dumps({"is_error": False, "content": "read"}),
                    },
                }
            )
        _rows(keep, rows)
        item = {"path": str(self.folder / key), "copy": str(keep)}
        stopped = self.stops[i - 1] if i <= len(self.stops) else None
        return CallResult(
            f"Answer {i}.",
            json.dumps(
                {
                    "commands": [],
                    "outputs": [],
                    "files": [],
                    "events": [],
                    "stdout": "",
                    "stderr": "",
                }
            ),
            None if stopped else 0,
            {},
            {"thread_id": key, "native_sessions": [item], "stopped": stopped},
            "",
            [],
        )


def _driver(
    tmp_path, messages, *, limit=1000, seconds=30, shape="interactive", stops=(), tool=None
):
    stage, workspace, results = (tmp_path / name for name in ("stage", "workspace", "results"))
    for folder in (stage, workspace, results):
        folder.mkdir()
    program = stage / "next.py"
    program.write_text(
        "import json,os\nmessages="
        + repr(messages)
        + '\nn=int(os.environ["OB_TURN"])-1\n'
        + "print(json.dumps(messages[n] if n<len(messages) else "
        + '{"end":True,"reason":"complete"}))\n',
        encoding="utf-8",
    )
    session = Session(
        shape,
        10,
        2,
        seconds,
        limit,
        (sys.executable, str(program)),
        ("opener", "status", "info", "note", "nudge", "unknown", "ruling", "directive", "answer"),
        20 if shape == "split" else None,
        "Resume.",
    )
    harness = FakeHarness(tmp_path, stops, tool)
    place = Driving(
        workspace, (), os.environ["PATH"], results / "run.native.jsonl", stage, dict(os.environ)
    )
    return Driver(
        session, "Start.", Request("test", "medium", session_run=True), harness, place
    ), harness


def test_gap_is_excluded_from_active_time_and_timeout_is_cumulative(tmp_path):
    driver, harness = _driver(
        tmp_path, [{"label": "status", "message": "Go.", "wait_seconds": 0.1}]
    )
    result = driver.run()
    assert len(harness.requests) == 2 and not result.extras.get("error")
    assert time.monotonic() - driver.started - result.extras["active_seconds"] >= 0.1
    assert result.extras["session_tokens"]["input_tokens"] == 200
    assert harness.requests[1].budget.seconds < harness.requests[0].budget.seconds - 0.1


def test_timeout_during_gap_never_sends_the_waiting_turn(tmp_path):
    driver, harness = _driver(
        tmp_path, [{"label": "status", "message": "Go.", "wait_seconds": 2}], seconds=0.5
    )
    result = driver.run()
    assert len(harness.requests) == 1
    assert result.extras["stopped"] == "timeout" and not result.extras.get("error")


@pytest.mark.parametrize(
    ("stdout", "stderr", "expected_stdout", "expected_stderr"),
    [
        (b"partial\xff", b"failed\xfe", "partial\ufffd", "failed\ufffd"),
        ("partial", "failed", "partial", "failed"),
        (None, None, "", ""),
    ],
)
@pytest.mark.parametrize("expired", [False, True])
def test_next_turn_timeout_keeps_partial_output_as_text(
    tmp_path, monkeypatch, stdout, stderr, expected_stdout, expected_stderr, expired
):
    """Catches byte timeout output crashing evidence retention or hiding the timeout verdict."""
    from evals import long_sessions

    driver, _ = _driver(tmp_path, [])
    driver.call(driver.base)
    monkeypatch.setattr(driver, "seconds_left", lambda: 0 if expired else 1)

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1, output=stdout, stderr=stderr)

    monkeypatch.setattr(long_sessions, "bounded_command", timeout)
    assert driver.next_turn() is None
    assert driver.file(".next-1.stdout.txt").read_text(encoding="utf-8") == expected_stdout
    assert driver.file(".next-1.stderr.txt").read_text(encoding="utf-8") == expected_stderr
    if expired:
        assert driver.extras["stopped"] == "timeout" and "void" not in driver.extras
    else:
        assert driver.extras["void"] == "runner" and "next_turn" in driver.extras["error"]


def test_split_starts_fresh_and_keeps_the_session_input_budget(tmp_path):
    driver, harness = _driver(tmp_path, [], shape="split", limit=200, stops=("split",))
    subprocess.run(["git", "init", "-q", str(driver.place.workspace)], check=True)
    (driver.place.workspace / "work").write_text("done", encoding="utf-8")
    subprocess.run(["git", "-C", str(driver.place.workspace), "add", "work"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(driver.place.workspace),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "checkpoint",
        ],
        check=True,
    )
    result = driver.run()
    assert len(harness.requests) == 2
    assert harness.requests[1].resume == "" and harness.requests[1].reuse_cell
    assert harness.requests[1].budget.input_cap == 100
    assert result.extras["session_tokens"]["input_tokens"] == 200
    snapshot = json.loads(Path(result.extras["cut_state"]).read_text(encoding="utf-8"))
    assert "checkpoint" in snapshot["git_log"] and snapshot["git_status"] == ""
    assert (
        snapshot["files"]["work"]["sha256"]
        == "a4c3ed04a95a3da14a9d235c83d868bed7c0f45cf7f3faa751ee8f50598d2211"
    )


@pytest.mark.parametrize("stop", ["cut_after_calls", None])
def test_safety_limit_is_a_graded_stop_even_when_the_cli_ends_before_polling(tmp_path, stop):
    """Catches a missed cut that voids the run, or restarts it, instead of grading it as is."""
    driver, harness = _driver(tmp_path, [], shape="split", stops=(stop,))
    driver.session = driver.session._replace(cut_after_calls=1)
    result = driver.run()
    assert len(harness.requests) == 1 and not result.extras.get("void")
    assert result.extras["stopped"] == "cut_after_calls" and result.extras["split_reached"] is False


def test_protocol_defect_voids_instead_of_model_failure(tmp_path):
    driver, harness = _driver(
        tmp_path, [{"end": True, "reason": "undefined", "protocol_defect": True}]
    )
    result = driver.run()
    assert len(harness.requests) == 1 and result.extras["void"] == "protocol_defect"
    assert result.extras["stopped"] is None


def test_protected_tool_reference_keeps_attempt_with_intact_seals(tmp_path):
    # The grading stage's own file: a relative `person.json` would resolve inside the workspace.
    person = str(tmp_path / "stage" / "person.json")
    driver, harness = _driver(tmp_path, [], tool=json.dumps({"file": person}))
    result = driver.run()
    assert len(harness.requests) == 1 and not result.extras.get("void")
    evidence = json.loads(Path(result.extras["contamination_file"]).read_text(encoding="utf-8"))
    assert evidence[0]["name"] == "Read" and evidence[0]["target"] == str(tmp_path / "stage")

    assert evidence[0]["classification"] == "attempt"
    assert evidence[0]["call_id"]
    assert result.extras["isolation_verdict"] == "PASS"


@pytest.mark.parametrize("wait", [-1, 7201, True, None, float("inf"), float("nan")])
def test_wait_seconds_refuses_invalid_values(wait):
    with pytest.raises(SessionError, match="wait_seconds"):
        next_message(
            json.dumps({"label": "info", "message": "Go.", "wait_seconds": wait}), ("info",)
        )


@pytest.mark.parametrize("wait", [0, 0.1, 7200])
def test_wait_seconds_accepts_the_closed_range(wait):
    assert (
        next_message(
            json.dumps({"label": "unknown", "message": "Your call.", "wait_seconds": wait}),
            ("unknown",),
        )["wait_seconds"]
        == wait
    )


@pytest.mark.parametrize("void", ["contaminated", "protocol_defect", "runner"])
def test_void_never_calls_a_grader(tmp_path, monkeypatch, void):
    def refused(*args):
        pytest.fail("a void run was graded")

    monkeypatch.setattr(RUN, "post_check", refused)
    extra = {"void": void}
    report = RUN.grade(
        "session-example", tmp_path, RUN.Left(None, "kept", "answer", None), (True, ""), extra
    )
    assert extra["verdict"] == "UNVERIFIED" and extra["claims"] == {}
    assert void in report


@needs_posix_bash
def test_split_kills_without_warning_and_waits_for_detached_child(tmp_path):
    script = tmp_path / "session.py"
    script.write_text(
        """import os,signal,subprocess,sys,time
from pathlib import Path
for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, lambda *_: Path("warning").write_text("graceful"))
child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"], start_new_session=True)
Path("child").write_text(str(child.pid))
print("ready",flush=True)
time.sleep(60)
""",
        encoding="utf-8",
    )
    result = watched_command(
        [sys.executable, str(script)],
        cwd=str(tmp_path),
        timeout=10,
        interval=0.02,
        poll=lambda printed: "split" if "ready" in printed() else None,
    )
    assert result.stopped == "split" and not (tmp_path / "warning").exists()
    pid = int((tmp_path / "child").read_text(encoding="utf-8"))
    from evals.processes import _process_table

    table = _process_table()
    assert table is not None, "process table unavailable; cleanup is unverified"
    assert table.get(pid, (0, "Z"))[1] == "Z"


def test_cut_check_runs_from_stage_and_is_polled_at_five_seconds(tmp_path, monkeypatch):
    from evals import long_sessions

    driver, _ = _driver(tmp_path, [], shape="split")
    program = driver.place.stage / "cut.py"
    program.write_text(
        "import os,sys\nfrom pathlib import Path\n"
        'sys.exit(0 if Path(os.environ["OB_WORKSPACE"], "checkpoint").exists() else 1)\n',
        encoding="utf-8",
    )
    driver.session = driver.session._replace(cut_check=(sys.executable, str(program)))
    clock = [time.monotonic()]
    monkeypatch.setattr(long_sessions.time, "monotonic", lambda: clock[0])
    assert driver.cut_check() is None
    (driver.place.workspace / "checkpoint").write_text("done", encoding="utf-8")
    clock[0] += 4.9
    assert driver.cut_check() is None
    clock[0] += 0.1
    assert driver.cut_check() == "split"
    records = sorted(driver.place.keep.parent.glob("*.cut-check-*.json"))
    assert [json.loads(p.read_text(encoding="utf-8"))["returncode"] for p in records] == [1, 0]


def test_cut_program_outside_the_stage_is_a_runner_fault(tmp_path):
    driver, _ = _driver(tmp_path, [], shape="split")
    program = tmp_path / "outside.py"
    program.write_text("raise RuntimeError('must not run')\n", encoding="utf-8")
    driver.session = driver.session._replace(cut_check=(sys.executable, str(program)))
    with pytest.raises(SessionError, match="grading stage"):
        driver.cut_check()


def test_budget_carries_input_across_resumed_turns(tmp_path):
    driver, harness = _driver(tmp_path, [{"label": "info", "message": "Again."}] * 3, limit=200)
    result = driver.run()
    assert len(harness.requests) == 2
    assert [r.budget.input_cap for r in harness.requests] == [200, 100]
    assert result.extras["session_tokens"]["input_tokens"] == 200
    assert result.extras["stopped"] == "input_cap"


def test_unknown_tool_claims_are_unverified_even_if_the_grader_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        RUN, "post_check", lambda *args: ("PASS", "VERDICT: PASS\nPASS safe [static]\n", None)
    )
    monkeypatch.setattr(RUN, "human_read", lambda *args: False)
    monkeypatch.setattr(RUN, "required_claims", lambda *args: {"safe": True})
    extra: dict[str, Any] = {"unknown_tools": ["mystery"]}
    report = RUN.grade(
        "session-example", tmp_path, RUN.Left(None, "kept", "answer", None), (True, ""), extra
    )
    assert extra["verdict"] == "UNVERIFIED" and extra["claims"] == {"safe": "UNVERIFIED"}
    assert extra["checks_claims"] == {"safe": "PASS"}
    assert "VERDICT: UNVERIFIED" in report and "UNVERIFIED safe [" in report


def test_session_and_brief_prefixes_have_clean_home_guards(tmp_path):
    for name in ("session-example", "brief-example", "replica-example"):
        assert name.startswith(RUN.NAMED_ONLY)
        assert name.startswith(RUN.CLEAN_HOME)
        home = tmp_path / name
        home.mkdir()
        (home / "AGENTS.md").write_text("Private instructions.\n", encoding="utf-8")
        assert RUN.unclean_reach([name], home, tmp_path)


def test_split_waits_for_the_last_observed_process_before_returning(monkeypatch):
    from evals import processes, watch
    from outcomebound_tools import programs

    process = Mock(spec=subprocess.Popen, pid=101)
    process.wait.return_value = -9
    signs = []
    tables = iter([{202: (1, "T")}, {}])
    monkeypatch.setattr(processes, "stop_descendants", lambda pid: {202})
    monkeypatch.setattr(processes, "_process_table", lambda: next(tables))
    monkeypatch.setattr(watch.os, "killpg", lambda pid, sig: signs.append((pid, sig)))
    monkeypatch.setattr(watch.os, "getpgid", lambda pid: 101)
    monkeypatch.setattr(programs, "stop_tree", lambda process: None)
    watch._interrupt(process)
    assert signs == [(101, watch.signal.SIGKILL)]
    assert list(tables) == []


def test_unavailable_process_table_refuses_a_split_restart(monkeypatch):
    from evals import processes, watch
    from outcomebound_tools import programs

    process = Mock(spec=subprocess.Popen, pid=101)
    process.wait.return_value = -9
    monkeypatch.setattr(processes, "stop_descendants", lambda pid: set())
    monkeypatch.setattr(processes, "_process_table", lambda: None)
    monkeypatch.setattr(watch.os, "killpg", lambda *args: None)
    monkeypatch.setattr(programs, "stop_tree", lambda process: None)
    with pytest.raises(ValueError, match="cannot verify"):
        watch._interrupt(process)


def test_claude_cumulative_reconciliation_uses_only_the_current_turn(tmp_path):
    from evals.harnesses.claude_code import native_reconciliation

    first = {
        "type": "assistant",
        "message": {
            "id": "first",
            "usage": {
                "input_tokens": 10,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 10,
                "output_tokens": 5,
            },
        },
    }
    second = {
        "type": "assistant",
        "message": {
            "id": "second",
            "usage": {
                "input_tokens": 20,
                "cache_read_input_tokens": 70,
                "cache_creation_input_tokens": 10,
                "output_tokens": 7,
            },
        },
    }
    source = tmp_path / "session.jsonl"
    _rows(source, [first])
    before = {source: source.read_bytes()}
    _rows(source, [first, second])
    cumulative = {
        "input_tokens": 100,
        "cached_input_tokens": 70,
        "cache_creation_input_tokens": 10,
        "output_tokens": 7,
    }
    assert native_reconciliation(tmp_path, before, cumulative, "parent") == []
    (mismatch,) = native_reconciliation(
        tmp_path, before, {**cumulative, "output_tokens": 8}, "parent"
    )
    assert mismatch["per_call"]["output_tokens"] == 7
    assert mismatch["cumulative"]["output_tokens"] == 8


def test_claude_retained_files_do_not_split_one_native_session(tmp_path):
    row = {
        "type": "assistant",
        "sessionId": "parent",
        "message": {
            "id": "call",
            "usage": {
                "input_tokens": 10,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 10,
                "output_tokens": 5,
            },
        },
    }
    one = _rows(tmp_path / "one.jsonl", [row])
    two = _rows(tmp_path / "two.jsonl", [row])
    usage = NativeUsage("claude-code")
    assert usage.add({"thread_id": "parent", "native_sessions": [one]})[0] == 1
    assert usage.add({"thread_id": "parent", "native_sessions": [two]})[0] == 0
    assert usage.total()["input_tokens"] == 100


@pytest.mark.parametrize(
    "counts",
    [
        None,
        {
            "input_tokens": 100,
            "cached_input_tokens": 0,
            "output_tokens": 10,
            "reasoning_output_tokens": 0,
        },
    ],
)
def test_native_usage_refuses_missing_per_call_counts(tmp_path, counts):
    rows = [_meta("parent")]
    if counts is not None:
        rows.append(
            {
                "type": "event_msg",
                "payload": {"type": "token_count", "info": {"total_token_usage": counts}},
            }
        )
    item = _rows(tmp_path / "native.jsonl", rows)
    with pytest.raises(ValueError, match=r"no (per-call token counts|last_token_usage)"):
        NativeUsage("codex").add({"native_sessions": [item]})
