"""The Claude Code harness: its stream decoder, its loading check, its call and its place in
run.py and loop.py.

No test here calls a model. A call runs a fake `claude`, a Python program that prints a
stream-JSON stream and writes a native session as the shapes the Agent SDK documents, and the
CLI's own start event, describe them; every stream below is synthetic.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from evals import claude_stream as cs
from evals.harnesses import Budget, Request
from evals.harnesses import claude_code as cc
from tests.eval_helpers import ROOT, RUN, load
from tests.portable import needs_posix_bash

SESSION = "3f6c2a10-1111-4222-8333-444455556666"
MODEL = "model-test"
USAGE = {
    "input_tokens": 200,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 800,
    "output_tokens": 10,
}


# --- synthetic streams -----------------------------------------------------------------------


def _start(**changes: Any) -> dict[str, Any]:
    return {
        "type": "system",
        "subtype": "init",
        "cwd": "/ws",
        "session_id": SESSION,
        "model": MODEL,
        "permissionMode": "acceptEdits",
        "apiKeySource": "none",
        "claude_code_version": "2.1.999",
        "tools": ["Bash", "Read", "Edit", "Write"],
        "mcp_servers": [],
        "skills": ["update-config"],
        "plugins": [{"name": "agents-md", "path": "/built/in", "source": "agents-md@builtin"}],
        **changes,
    }


def _reply(number: int, *parts: dict[str, Any]) -> dict[str, Any]:
    message = {"id": f"msg_{number}", "role": "assistant", "model": MODEL, "content": list(parts)}
    return {"type": "assistant", "message": {**message, "usage": USAGE}, "session_id": SESSION}


def _use(key: str, name: str, **args: Any) -> dict[str, Any]:
    return {"type": "tool_use", "id": key, "name": name, "input": args}


def _result(key: str, content: Any = "ok", error: bool = False) -> dict[str, Any]:
    part = {"type": "tool_result", "tool_use_id": key, "content": content, "is_error": error}
    return {"type": "user", "message": {"role": "user", "content": [part]}, "session_id": SESSION}


def _end(**changes: Any) -> dict[str, Any]:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 3,
        "result": "Done.",
        "total_cost_usd": 0.0123,
        "usage": {**USAGE, "output_tokens": 30},
        "modelUsage": {
            MODEL: {
                "inputTokens": 600,
                "outputTokens": 30,
                "cacheReadInputTokens": 2400,
                "cacheCreationInputTokens": 0,
                "costUSD": 0.0123,
            }
        },
        "permission_denials": [],
        "session_id": SESSION,
        **changes,
    }


def _stream(*events: dict[str, Any]) -> str:
    return "".join(json.dumps(event) + "\n" for event in events)


WHOLE = [
    _start(),
    _reply(1, _use("t1", "Bash", command="cd /ws && make test")),
    _result("t1", "2 passed"),
    _reply(2, _use("t2", "Read", file_path="/ws/a.py"), _use("t3", "Edit", file_path="/ws/a.py")),
    _result("t2"),
    _result("t3", "File has not been read yet", error=True),
    _reply(3, _use("t4", "Write", file_path="/ws/b.py"), _use("t5", "Bash", command="rm -rf /")),
    _result("t4"),
    _result("t5", "Permission denied", error=True),
    _end(permission_denials=[{"tool_name": "Bash", "tool_use_id": "t5", "tool_input": {}}]),
]


def test_a_stream_gives_bash_commands_and_read_edit_write_file_events_apart() -> None:
    """Breaks if a file tool becomes a command, or a Read, Edit or Write leaves no record."""

    transcript, decoded = cs.stream_transcript(_stream(*WHOLE), "", {"t1": "/ws"})
    document = json.loads(transcript)
    assert document["format"] == "outcomebound-command-events-v1"
    assert document["commands"] == [["make test", "succeeded", "/ws"], ["rm -rf /", "declined", ""]]
    assert document["outputs"] == ["2 passed", "Permission denied"]
    assert document["files"] == [
        ["Read", "/ws/a.py", "succeeded"],
        ["Edit", "/ws/a.py", "failed"],
        ["Write", "/ws/b.py", "succeeded"],
    ]
    assert len(document["events"]) == len(WHOLE)
    assert decoded.answer == "Done." and decoded.unknown == []
    assert decoded.tools == {"Bash": 2, "Read": 1, "Edit": 1, "Write": 1}
    grader = load("transcript_commands_for_claude", "evals/graders/transcript_commands.py")
    assert [record[0] for record in grader.execution_records(transcript)] == [
        "make test",
        "rm -rf /",
    ], "the graders read the Claude Code transcript as they read codex's"


@pytest.mark.parametrize(
    ("events", "why"),
    [
        (WHOLE[:-1], "no final result event: a stopped call"),
        ([*WHOLE[:2], *WHOLE[3:]], "a call with no result"),
        ([*WHOLE[:-1], _result("t9"), WHOLE[-1]], "a result with no call"),
        (
            [WHOLE[0], _reply(1, _use("a1", "Agent", prompt="x")), _result("a1"), WHOLE[-1]],
            "a subagent",
        ),
        (WHOLE[1:], "no start event"),
    ],
)
def test_NEGATIVE_CONTROL_a_stream_that_cannot_show_every_call_has_no_commands_or_files(
    events: list[dict[str, Any]], why: str
) -> None:
    document = json.loads(cs.stream_transcript(_stream(*events), "")[0])
    assert document["commands"] is None and document["files"] is None, why


def test_a_passive_tool_is_no_command_and_a_skill_invocation_is_kept() -> None:
    events = [
        _start(),
        _reply(1, _use("g1", "Grep", pattern="x"), _use("s1", "Skill", skill="diagnose")),
        _result("g1"),
        _result("s1"),
        _end(),
    ]
    decoded = cs.decode(events)
    assert decoded.commands == [] and decoded.files == [] and decoded.skills == ["diagnose"]


def test_the_session_s_tokens_and_list_price_cost_come_from_the_result_event() -> None:
    tokens = cs.session_tokens(WHOLE)
    assert tokens is not None
    assert (tokens["input_tokens"], tokens["cached_input_tokens"], tokens["output_tokens"]) == (
        3000,
        2400,
        30,
    )
    assert tokens["cost_usd"] == 0.0123 and tokens["reasoning_in_output"] is True
    assert tokens["source"] == "stream-result-model-usage"
    plain = cs.session_tokens([*WHOLE[:-1], _end(modelUsage={})])
    assert plain is not None and plain["input_tokens"] == 1000 and plain["output_tokens"] == 30


def test_a_stopped_call_s_tokens_count_each_assistant_message_once() -> None:
    repeated = _reply(1, {"type": "text", "text": "a"})
    tokens = cs.session_tokens([_start(), repeated, repeated, _reply(2)])
    assert tokens is not None
    assert (tokens["input_tokens"], tokens["cached_input_tokens"]) == (2000, 1600)
    assert tokens["cost_usd"] is None and tokens["source"] == "stream-assistant"


def test_the_meter_reads_only_complete_lines_and_counts_a_message_once() -> None:
    meter = cs.StreamMeter()
    line = json.dumps(_reply(1)) + "\n"
    assert meter.input(line[:20]) is None
    assert meter.input(line) == 1000
    assert meter.input(line + line) == 1000, "a repeated message counts once"
    assert meter.input(line + line + json.dumps(_reply(2)) + "\n") == 2000


# --- the loading check -------------------------------------------------------------------------


def _verdicts(rows: list[list[str]]) -> dict[str, str]:
    return {row[0]: row[1] for row in rows}


OB_SKILLS = ("diagnose", "using-outcomebound")


def test_a_cell_that_loads_what_its_arm_gives_passes_and_what_no_event_names_stays_unverified() -> (
    None
):
    expected = cs.Expected((), ("diagnose",), ("using-outcomebound",))
    rows = cs.loading_check([_start(skills=["update-config", "diagnose"])], expected)
    assert _verdicts(rows) == {
        "start-event": "PASS",
        "plugins": "PASS",
        "skills": "PASS",
        "mcp-servers": "PASS",
        "hooks": "UNVERIFIED",
        "instruction-files": "UNVERIFIED",
    }


@pytest.mark.parametrize(
    ("change", "item"),
    [
        ({"plugins": [{"name": "stray", "path": "/p/stray", "source": "stray@market"}]}, "plugins"),
        ({"skills": ["using-outcomebound"]}, "skills"),
        ({"skills": ["stray:tidy"]}, "skills"),
        ({"skills": []}, "skills"),
        ({"mcp_servers": [{"name": "claude.ai Mail", "status": "connected"}]}, "mcp-servers"),
    ],
)
def test_NEGATIVE_CONTROL_a_plugin_skill_or_server_the_arm_does_not_add_fails_the_cell(
    change: dict[str, Any], item: str
) -> None:
    expected = cs.Expected((), ("diagnose",), ("using-outcomebound",))
    start = _start(**{"skills": ["diagnose"], **change})
    assert _verdicts(cs.loading_check([start], expected))[item] == "FAIL"


def test_NEGATIVE_CONTROL_a_hook_that_runs_in_an_arm_that_adds_none_fails_the_cell() -> None:
    start = _start()
    events = cs.leaked_start(start)
    rows = _verdicts(cs.loading_check(events, cs.Expected()))
    assert rows["hooks"] == "FAIL" and rows["plugins"] == "FAIL"


@pytest.mark.parametrize("field", ["plugins", "skills", "mcp_servers"])
def test_NEGATIVE_CONTROL_a_field_the_start_event_lacks_is_unverified_never_a_pass(
    field: str,
) -> None:
    start = {key: value for key, value in _start().items() if key != field}
    item = field.replace("_", "-")
    assert _verdicts(cs.loading_check([start], cs.Expected()))[item] == "UNVERIFIED"
    assert _verdicts(cs.loading_check([], cs.Expected())) == {"start-event": "FAIL"}


def test_a_plugin_arm_passes_with_its_own_plugin_and_skills_and_fails_without_them(
    tmp_path: Path,
) -> None:
    clone = tmp_path / "third-party" / "tidy"
    clone.mkdir(parents=True)
    expected = cs.Expected((clone,), (), OB_SKILLS)
    own = {"name": "tidy", "path": str(clone), "source": "tidy@inline"}
    start = _start(plugins=[own], skills=["tidy:trim", "update-config"])
    hook = cs.leaked_start(start)[1]
    rows = _verdicts(cs.loading_check([start, hook], expected))
    assert rows["plugins"] == "PASS" and rows["skills"] == "PASS" and rows["hooks"] == "UNVERIFIED"
    assert _verdicts(cs.loading_check([_start()], expected))["plugins"] == "FAIL"


# --- what a call reaches before it runs --------------------------------------------------------


def test_NEGATIVE_CONTROL_an_instruction_or_rules_file_above_the_workspace_fails_the_reach(
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "root" / "ws"
    workdir.mkdir(parents=True)
    clean = _verdicts(cs.reach_rows(workdir))
    assert clean["nothing-above-workspace"] == "PASS"
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / ".claude" / "rules" / "keep.md").write_text("Keep.\n", encoding="utf-8")
    (tmp_path / "root" / "CLAUDE.md").write_text("Be brief.\n", encoding="utf-8")
    row = next(r for r in cs.reach_rows(workdir) if r[0] == "nothing-above-workspace")
    assert row[1] == "FAIL" and "CLAUDE.md" in row[2] and "keep.md" in row[2]
    (workdir / "x").mkdir()
    fresh = _verdicts(cs.reach_rows(tmp_path / "other", (workdir,)))
    assert fresh["fresh-home"] == "FAIL", "a cell folder that holds something is not new"


def test_a_managed_policy_that_loads_code_or_instructions_fails_and_other_keys_apply_alike(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cs, "MANAGED", {"test": tmp_path})
    settings = tmp_path / "managed-settings.json"
    settings.write_text(json.dumps({"cleanupPeriodDays": 30}), encoding="utf-8")
    assert cs.managed("test") == ([], [f"{settings} sets cleanupPeriodDays"])
    settings.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    assert cs.managed("test")[0] == [f"{settings} sets hooks"]
    (tmp_path / "CLAUDE.md").write_text("Policy.\n", encoding="utf-8")
    assert len(cs.managed("test")[0]) == 2
    assert cs.managed("elsewhere") == ([], [])


# --- the harness, with a fake claude ------------------------------------------------------------

# claude, faked as a Python program. `--version` and `auth status` answer at once. A call
# records its argv, environment and prompt to $FAKE_RECORD, prints the start event, then either
# runs to its end (a Bash call of the `probe` stub where one is on PATH, a Read, an Edit, a
# denied Bash call, the result event), or, with $FAKE_SLOW, prints an assistant message of 1000
# input tokens every fifth of a second and never ends; with $FAKE_TOUCH it rewrites
# notes.txt and puts it back once the watch log the call protects holds the write. It writes
# the native session under $CLAUDE_CONFIG_DIR/projects/ as it goes, the model and effort on
# each assistant record ($FAKE_EFFORT overrides the effort). $FAKE_STRAY adds a plugin the arm
# does not give, $FAKE_HOOK a hook event.
FAKE_CLAUDE = r"""#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path

argv = sys.argv[1:]
if argv[:1] == ["--version"]:
    print("2.1.999 (Claude Code)")
    sys.exit(0)
if argv[:2] == ["auth", "status"]:
    print(os.environ.get("FAKE_AUTH", "{}"))
    sys.exit(0)
prompt = sys.stdin.read()
def opt(name):
    return argv[argv.index(name) + 1] if name in argv else None
cwd = os.getcwd()
if os.environ.get("FAKE_RECORD"):
    Path(os.environ["FAKE_RECORD"]).write_text(json.dumps(
        {"argv": argv, "env": dict(os.environ), "prompt": prompt, "cwd": cwd}))
key = "3f6c2a10-1111-4222-8333-444455556666"
model, effort = opt("--model"), os.environ.get("FAKE_EFFORT") or opt("--effort")
folder = Path(os.environ["CLAUDE_CONFIG_DIR"], "projects", cwd.replace("/", "-"))
folder.mkdir(parents=True, exist_ok=True)
session = open(folder / f"{key}.jsonl", "w")
def native(record):
    session.write(json.dumps({**record, "sessionId": key}) + "\n")
    session.flush()
def emit(event):
    print(json.dumps({**event, "session_id": key}), flush=True)
dirs = [argv[i + 1] for i, word in enumerate(argv) if word == "--plugin-dir"]
plugins = [{"name": Path(d).name, "path": d, "source": Path(d).name + "@inline"} for d in dirs]
plugins.append({"name": "agents-md", "path": "/built/in", "source": "agents-md@builtin"})
if os.environ.get("FAKE_STRAY"):
    plugins.append({"name": "stray", "path": "/p/stray", "source": "stray@market"})
skills = sorted(p.parent.name for p in Path(cwd, ".claude", "skills").glob("*/SKILL.md"))
skills += ["update-config"] + [Path(d).name + ":trim" for d in dirs]
native({"type": "user", "cwd": cwd, "message": {"role": "user", "content": prompt}})
emit({"type": "system", "subtype": "init", "cwd": cwd, "model": model,
      "permissionMode": opt("--permission-mode"), "apiKeySource": "none",
      "claude_code_version": "2.1.999", "tools": ["Bash", "Read", "Edit", "Write"],
      "mcp_servers": [], "skills": skills, "plugins": plugins})
if os.environ.get("FAKE_HOOK"):
    emit({"type": "system", "subtype": "hook_started", "hook_id": "h", "hook_name": "x",
          "hook_event": "SessionStart"})
usage = {"input_tokens": 200, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 800,
         "output_tokens": 10}
def reply(n, *parts):
    message = {"id": f"msg_{n}", "role": "assistant", "model": model, "content": list(parts),
               "usage": usage}
    native({"type": "assistant", "cwd": cwd, "effort": effort, "isSidechain": False,
            "message": message})
    emit({"type": "assistant", "message": message, "parent_tool_use_id": None})
def answer(key, content, error=False):
    part = {"type": "tool_result", "tool_use_id": key, "content": content, "is_error": error}
    emit({"type": "user", "message": {"role": "user", "content": [part]},
          "parent_tool_use_id": None})
if os.environ.get("FAKE_SLOW"):
    if os.environ.get("FAKE_TOUCH"):
        settings = json.loads(opt("--settings"))
        log = next(Path(p) for p in settings["sandbox"]["filesystem"]["denyWrite"]
                   if p.endswith(".watch.jsonl"))
        notes = Path(cwd, "notes.txt")
        seed = notes.read_text()
        notes.write_text("rewritten\n")
        deadline = time.monotonic() + 20
        while not (log.is_file() and log.read_text()) and time.monotonic() < deadline:
            time.sleep(0.05)
        notes.write_text(seed)
    for n in range(1, 1000):
        reply(n, {"type": "text", "text": "working"})
        time.sleep(0.2)
    sys.exit(0)
ran = subprocess.run(["probe"], capture_output=True, text=True)
def use(key, name, **args):
    return {"type": "tool_use", "id": key, "name": name, "input": args}
reply(1, use("t1", "Bash", command=f"cd {cwd} && probe"))
answer("t1", ran.stdout if ran.returncode == 0 else ran.stderr, ran.returncode != 0)
reply(2, use("t2", "Read", file_path=f"{cwd}/notes.txt"),
      use("t3", "Edit", file_path=f"{cwd}/notes.txt"))
answer("t2", "seed")
answer("t3", "edited")
reply(3, use("t4", "Bash", command="curl example.com"))
answer("t4", "Permission to use Bash has been denied.", True)
reply(4, {"type": "text", "text": "Done."})
emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 4, "result": "Done.",
      "total_cost_usd": 0.02,
      "usage": {**usage, "output_tokens": 40},
      "modelUsage": {model: {"inputTokens": 800, "outputTokens": 40, "cacheReadInputTokens": 3200,
                             "cacheCreationInputTokens": 0, "costUSD": 0.02}},
      "permission_denials": [{"tool_name": "Bash", "tool_use_id": "t4", "tool_input": {}}]})
"""

STUB = '#!/bin/sh\necho "probe ran"\n'


def _trusted() -> Path:
    """A folder outside every path the call may write (the system's temporary folders among
    them), as a run's evidence and cell must be."""

    base = ROOT / ".agents" / "work" / "eval-native-tests"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="claude-", dir=base))


@pytest.fixture
def trusted() -> Any:
    folder = _trusted()
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    """A folder holding the fake `claude` and a `probe` stub, for the front of a call's PATH."""

    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, text in (("claude", FAKE_CLAUDE), ("probe", STUB)):
        (bindir / name).write_text(text, encoding="utf-8")
        (bindir / name).chmod(0o755)
    return bindir


OPERATOR = {
    "CLAUDECODE": "1",
    "CLAUDE_CODE_ENTRYPOINT": "cli",
    "CLAUDE_CODE_OAUTH_TOKEN": "token-for-the-test",
    "ANTHROPIC_MODEL": "other-model",
    "PONYTAIL_HOME": "/somewhere",
    "XDG_CONFIG_HOME": "/operator/config",
    "DISABLE_MICROCOMPACT": "1",
    "MCP_TIMEOUT": "5",
    "API_TIMEOUT_MS": "1",
}


def _harness(
    record: Path, env: dict[str, str] | None = None, plugins: tuple[Path, ...] = ()
) -> cc.ClaudeCodeHarness:
    base = {**os.environ, **OPERATOR, "FAKE_RECORD": str(record), **(env or {})}
    return cc.ClaudeCodeHarness(lambda: base, RUN._run, 60, plugins)


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    (workspace / ".claude" / "skills" / "diagnose").mkdir(parents=True)
    (workspace / ".claude" / "skills" / "diagnose" / "SKILL.md").write_text("x", encoding="utf-8")
    (workspace / "notes.txt").write_text("seed\n", encoding="utf-8")
    return workspace


def _call(
    tmp_path: Path,
    trusted: Path,
    fake: Path,
    request: Request | None = None,
    env: dict[str, str] | None = None,
) -> tuple[Any, dict[str, Any]]:
    record = tmp_path / "record.json"
    harness = _harness(record, env)
    result = harness.call(
        "Task: tidy.\n",
        request or Request(MODEL, "high"),
        _workspace(tmp_path),
        (),
        f"{fake}{os.pathsep}{os.environ['PATH']}",
        trusted / "kept.native.jsonl",
    )
    seen = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {}
    return result, seen


pytestmark = needs_posix_bash


def test_a_claude_code_call_is_identified_decoded_costed_and_checked_for_what_it_loaded(
    tmp_path: Path, trusted: Path, fake: Path
) -> None:
    result, _seen = _call(tmp_path, trusted, fake)
    assert result.error == "", result.checks
    assert {row[1] for row in result.checks} == {"PASS"}
    assert result.observed == {
        "model": MODEL,
        "effort": "high",
        "cwd": str((tmp_path / "ws").resolve()),
        "cli_version": "2.1.999",
    }
    assert result.answer == "Done." and result.returncode == 0
    document = json.loads(result.transcript)
    assert document["commands"] == [
        ["probe", "succeeded", str((tmp_path / "ws").resolve())],
        ["curl example.com", "declined", str((tmp_path / "ws").resolve())],
    ]
    assert document["outputs"][0] == "probe ran\n", "the stub ran from the call's PATH"
    assert [row[0] for row in document["files"]] == ["Read", "Edit"]
    extras = result.extras
    assert extras["harness"] == "claude-code" and extras["thread_id"] == SESSION
    assert extras["session_tokens"]["cost_usd"] == 0.02
    assert extras["session_tokens"]["input_tokens"] == 4000
    assert extras["void"] is None and extras["unknown_item_types"] == []
    assert not [row for row in extras["isolation"] if row[1] == "FAIL"]
    kept = trusted / "kept.native.jsonl"
    assert kept.is_file() and Path(extras["native_session"]).read_bytes() == kept.read_bytes()
    cell = trusted / "kept.claude-home"
    assert extras["claude_home"] == str(cell) and cell.is_dir(), "the cell and its session stay"


def test_a_call_runs_in_a_fresh_cell_with_none_of_the_operator_s_claude_setup(
    tmp_path: Path, trusted: Path, fake: Path
) -> None:
    """Breaks if the operator's Claude, Anthropic, Ponytail or XDG setting reaches a call, or
    the call's sandbox, permission mode or sources change."""

    _result, seen = _call(tmp_path, trusted, fake)
    env, argv = seen["env"], seen["argv"]
    cell = trusted / "kept.claude-home"
    assert env["HOME"] == str(cell / "home")
    assert env["CLAUDE_CONFIG_DIR"] == str(cell / "config")
    assert env["XDG_CONFIG_HOME"] == str(cell / "xdg" / "config")
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == OPERATOR["CLAUDE_CODE_OAUTH_TOKEN"]
    inherited = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_MODEL", "PONYTAIL_HOME")
    for name in (*inherited, "DISABLE_MICROCOMPACT", "MCP_TIMEOUT", "API_TIMEOUT_MS"):
        assert name not in env, name
    assert "ANTHROPIC_API_KEY" not in env
    assert argv[:5] == [
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-hook-events",
    ]
    for pair in (
        ["--permission-mode", "acceptEdits"],
        ["--permission-prompts", "none"],
        ["--setting-sources", "project,local"],
        ["--model", MODEL],
        ["--effort", "high"],
    ):
        index = argv.index(pair[0])
        assert argv[index : index + 2] == pair
    assert "--strict-mcp-config" in argv and "--plugin-dir" not in argv
    sandbox = json.loads(argv[argv.index("--settings") + 1])["sandbox"]
    assert sandbox["enabled"] and sandbox["failIfUnavailable"]
    assert not sandbox["allowUnsandboxedCommands"]
    assert sandbox["network"] == {"allowLocalBinding": False}
    assert sandbox["credentials"]["envVars"] == [
        {"name": "CLAUDE_CODE_OAUTH_TOKEN", "mode": "deny"}
    ]
    assert seen["prompt"] == "Task: tidy.\n"


@pytest.mark.parametrize(
    ("env", "words"),
    [
        ({"FAKE_STRAY": "1"}, "isolation: plugins"),
        ({"FAKE_HOOK": "1"}, "isolation: hooks"),
        ({"FAKE_EFFORT": "low"}, "effort low, not high"),
    ],
)
def test_NEGATIVE_CONTROL_a_call_that_loaded_more_or_ran_otherwise_does_not_count(
    tmp_path: Path, trusted: Path, fake: Path, env: dict[str, str], words: str
) -> None:
    result, _seen = _call(tmp_path, trusted, fake, env=env)
    assert words in result.error, result.error
    if words.startswith("isolation"):
        assert result.extras["void"] == "isolation"


def test_a_call_whose_input_passes_its_cap_is_stopped_and_still_identified(
    tmp_path: Path, trusted: Path, fake: Path
) -> None:
    started = time.monotonic()
    request = Request(MODEL, "high", budget=Budget(60, input_cap=2500))
    result, _seen = _call(tmp_path, trusted, fake, request=request, env={"FAKE_SLOW": "1"})
    assert time.monotonic() - started < 20, "the call ran on past its cap"
    assert result.extras["stopped"] == "input_cap" and result.returncode is None
    assert result.extras["input_seen_at_stop"] >= 3000
    assert result.error == "", result.checks
    tokens = result.extras["session_tokens"]
    assert tokens["source"] == "stream-assistant" and tokens["input_tokens"] >= 3000
    assert json.loads(result.transcript)["commands"] is None, "a stopped stream shows no end"


def test_a_call_that_runs_past_its_time_is_stopped_as_a_timeout(
    tmp_path: Path, trusted: Path, fake: Path
) -> None:
    result, _seen = _call(
        tmp_path,
        trusted,
        fake,
        request=Request(MODEL, "high", budget=Budget(2)),
        env={"FAKE_SLOW": "1"},
    )
    assert result.extras["stopped"] == "timeout" and result.returncode is None
    assert result.extras["budget_requested"] == {"seconds": 2, "input_cap": None}


def test_NEGATIVE_CONTROL_a_call_that_would_read_a_file_above_its_workspace_is_refused_first(
    tmp_path: Path, trusted: Path, fake: Path
) -> None:
    (tmp_path / "CLAUDE.md").write_text("Other rules.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nothing-above-workspace"):
        _call(tmp_path, trusted, fake)
    assert not (tmp_path / "record.json").exists(), "the fake claude never started"


def test_NEGATIVE_CONTROL_a_cell_that_exists_or_lies_in_the_model_s_reach_is_refused_first(
    tmp_path: Path, trusted: Path, fake: Path
) -> None:
    (trusted / "kept.claude-home").mkdir()
    with pytest.raises(FileExistsError):
        _call(tmp_path, trusted, fake)
    workspace = _workspace(tmp_path / "inner")
    harness = _harness(tmp_path / "record.json")
    with pytest.raises(ValueError, match="model writable root"):
        harness.call(
            "x", Request(MODEL, "high"), workspace, (), os.environ["PATH"], workspace / "k.jsonl"
        )
    assert not (tmp_path / "record.json").exists()


def test_a_plugin_arm_passes_its_clone_and_loads_it(
    tmp_path: Path, trusted: Path, fake: Path
) -> None:
    clone = tmp_path / "third-party" / "tidy"
    clone.mkdir(parents=True)
    record = tmp_path / "record.json"
    harness = _harness(record, plugins=(clone,))
    result = harness.call(
        "Task.\n",
        Request(MODEL, "high"),
        _workspace(tmp_path),
        (),
        f"{fake}{os.pathsep}{os.environ['PATH']}",
        trusted / "kept.native.jsonl",
    )
    argv = json.loads(record.read_text(encoding="utf-8"))["argv"]
    assert argv[argv.index("--plugin-dir") + 1] == str(clone.resolve())
    assert result.error == "", result.checks
    assert result.extras["plugin_dirs"] == [str(clone.resolve())]


@pytest.mark.parametrize(
    ("status", "ok"),
    [
        ({"loggedIn": True, "authMethod": "claude.ai"}, True),
        ({"loggedIn": True, "authMethod": "oauth_token"}, True),
        ({"loggedIn": True, "authMethod": "api_key", "apiKeySource": "ANTHROPIC_API_KEY"}, False),
        ({"loggedIn": False, "authMethod": "none"}, False),
    ],
)
def test_preflight_observes_a_subscription_sign_in_from_a_fresh_cell_with_no_model_call(
    status: dict[str, Any], ok: bool
) -> None:
    seen: list[dict[str, str]] = []

    def run_env(command: list[str], env: dict[str, str]) -> tuple[int, str, str]:
        assert command == ["claude", "auth", "status", "--json"]
        seen.append(env)
        return 0, json.dumps(status), ""

    harness = cc.ClaudeCodeHarness(lambda: {**OPERATOR, "PATH": "/bin"}, RUN._run, run_env=run_env)
    found = harness.preflight()
    assert found["ok"] is ok and found["auth"] == ("subscription" if ok else "not-observed")
    (env,) = seen
    assert env["HOME"] != os.environ.get("HOME") and "CLAUDECODE" not in env
    assert not Path(env["HOME"]).exists(), "the preflight's cell is removed after"


# --- run.py and loop.py ---------------------------------------------------------------------


@pytest.fixture
def claude_install() -> Any:
    RUN.set_harness(RUN.CLAUDE)
    yield
    RUN.set_harness(RUN.HARNESS)


def test_the_current_arm_on_claude_code_is_adopt_s_claude_code_install(
    claude_install: None,
) -> None:
    arm = RUN.load_arm("current")
    skills = [path for path in arm.files if path.endswith("/SKILL.md")]
    assert skills and all(path.startswith(".claude/skills/") for path in skills)
    assert RUN.element_of(".claude/skills/diagnose/SKILL.md") == "skill:diagnose"
    assert all(path.startswith(".claude/skills/") for _condition, path in arm.skills)
    RUN.set_harness(RUN.HARNESS)
    assert all(not path.startswith(".claude/") for path in RUN.load_arm("current").files)


def test_make_harness_names_claude_code_and_refuses_a_plugin_for_codex(tmp_path: Path) -> None:
    assert isinstance(RUN.make_harness(RUN.CLAUDE), cc.ClaudeCodeHarness)
    with pytest.raises(ValueError, match="takes none"):
        RUN.make_harness("codex", (tmp_path,))
    assert RUN._parser().parse_args(["--harness", "claude-code"]).harness == "claude-code"


def test_a_plugin_folder_must_be_a_clone_in_the_evals_home_s_third_party_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a plugin can come from anywhere but a pinned clone, a plugin cache among it."""

    monkeypatch.setenv("OB_EVALS_HOME", str(tmp_path / "evals-home"))
    clone = tmp_path / "evals-home" / "third-party" / "ponytail"
    clone.mkdir(parents=True)
    cache = tmp_path / "home" / ".claude" / "plugins" / "cache" / "ponytail"
    cache.mkdir(parents=True)
    escape = tmp_path / "evals-home" / "third-party" / "link"
    escape.symlink_to(cache)
    assert RUN.plugin_dir_refusal(str(clone)) == ""
    assert "not inside" in RUN.plugin_dir_refusal(str(cache))
    assert "not inside" in RUN.plugin_dir_refusal(str(escape)), "a link out of the clones"
    assert "not inside" in RUN.plugin_dir_refusal(str(clone.parent))
    assert "not an absolute path" in RUN.plugin_dir_refusal("third-party/ponytail")
    assert "not a folder" in RUN.plugin_dir_refusal(str(clone / "absent"))


LOOP = load("eval_loop_for_claude", "evals/loop.py")


def _plan(tmp_path: Path, **changes: Any) -> Path:
    plan = {
        "name": "claude1",
        "model": MODEL,
        "effort": "medium",
        "harness": "claude-code",
        "profile": "claude-top",
        "results": str(tmp_path / "results"),
        "workspaces": str(tmp_path / "workspaces"),
        "repetitions": [1],
        "fixtures": ["v2-ck-confined-budget"],
        "arms": [{"label": "none", "arm": "none"}],
        **changes,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def test_a_loop_plan_runs_claude_code_with_a_ponytail_plugin_arm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OB_EVALS_HOME", str(tmp_path / "evals-home"))
    clone = tmp_path / "evals-home" / "third-party" / "ponytail"
    clone.mkdir(parents=True)
    arms = [
        {"label": "none", "arm": "none"},
        {"label": "ponytail-plugin", "arm": "none", "plugin_dir": str(clone)},
    ]
    plan = LOOP.read_plan(_plan(tmp_path, arms=arms), LOOP.load_runner())
    words = {cell.arm.label: cell.argv for cell in LOOP.cells(plan)}
    plugin = words["ponytail-plugin"]
    assert plugin[plugin.index("--harness") + 1] == "claude-code"
    assert plugin[plugin.index("--plugin-dir") + 1] == str(clone)
    assert "--plugin-dir" not in words["none"]


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"profile": "attr"}, "profile attr runs on codex, not claude-code"),
        (
            {
                "harness": "codex",
                "profile": "",
                "arms": [{"label": "p", "arm": "none", "plugin_dir": "/x"}],
            },
            "plugin_dir needs harness claude-code",
        ),
        (
            {"arms": [{"label": "p", "arm": "none", "plugin_dir": "/elsewhere/ponytail"}]},
            "not a folder",
        ),
    ],
)
def test_NEGATIVE_CONTROL_a_claude_code_plan_that_mixes_profiles_or_takes_a_stray_plugin_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any], words: str
) -> None:
    monkeypatch.setenv("OB_EVALS_HOME", str(tmp_path / "evals-home"))
    with pytest.raises(LOOP.PlanError, match=words):
        LOOP.read_plan(_plan(tmp_path, **changes), LOOP.load_runner())


# --- a suite fixture's run, end to end with the fake claude ------------------------------------

# The check of the run below: the budget stop, the watch log and the stubs' digests reach it.
RECORDS_CHECK = r"""
import json, os, sys
from pathlib import Path

budget = json.loads(Path(os.environ["OB_EVAL_BUDGET"]).read_text())
assert budget["stopped"] == "input_cap" and budget["input"] > 5000, budget
assert budget["uncached"] * 5 == budget["input"], budget
lines = [json.loads(l) for l in Path(os.environ["OB_EVAL_WATCH_LOG"]).read_text().splitlines()]
assert [l["path"] for l in lines] == ["notes.txt", "notes.txt"], lines
digests = json.loads(Path(os.environ["OB_EVAL_STUB_DIGESTS"]).read_text())
assert digests["probe"]["before"] == digests["probe"]["after"], digests
print("records reached the check")
"""


def test_a_suite_run_on_claude_code_is_stopped_at_its_cap_with_its_watch_log_and_stubs(
    tmp_path: Path, trusted: Path, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the budget stop, the watcher or the stubs stop working for this harness: the
    fake rewrites a watched file and puts it back, and runs on until the cap stops it."""

    from tests.test_v2_runner import NAME, STATUS, _evals

    fixtures = _evals(tmp_path)
    (fixtures / NAME / "check.py").write_text(RECORDS_CHECK, encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    base = {**os.environ, "FAKE_SLOW": "1", "FAKE_TOUCH": "1"}
    harness = cc.ClaudeCodeHarness(lambda: base, RUN._run, 60)
    path = f"{fake}{os.pathsep}{os.environ['PATH']}"
    status = {**STATUS, "harness": "claude-code"}
    failed, row = RUN.run_one(trusted, status, NAME, RUN.load_arm("none"), path, harness)
    meta = json.loads((trusted / f"{NAME}.meta.json").read_text(encoding="utf-8"))
    assert not failed and meta["error"] == "", meta["error"]
    assert meta["claims"] == {"records-reach-checks": "PASS"}
    assert meta["verdict"] == "FAIL" and meta["checks_verdict"] == "PASS"
    assert meta["budget"]["stopped"] == "input_cap" and meta["watch_changes"] == 2
    assert meta["harness"] == row["harness"] == "claude-code" and row["thread_id"] == SESSION
    assert (trusted / f"{NAME}.native.jsonl").is_file()
    assert (trusted / f"{NAME}.claude-home" / "config" / "projects").is_dir()


def test_the_dry_run_builds_a_claude_code_cell_and_checks_the_loading_check_with_no_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], claude_install: None
) -> None:
    """The model-free dry run: adopt's Claude Code install, the exact argv and environment, and
    the loading check passing the expected load and failing a leak."""

    code = RUN._main(
        [
            "--dump-arm",
            "v2-ck-confined-budget",
            "--arm",
            "current",
            "--model",
            MODEL,
            "--harness",
            "claude-code",
            "--workspace-root",
            str(tmp_path / "root"),
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0, printed
    assert "loading-check-clean PASS" in printed and "loading-check-leak PASS" in printed
    assert "claude -p --output-format stream-json" in printed
    assert (
        "CLAUDE_CONFIG_DIR=" in printed and ".claude/skills/using-outcomebound/SKILL.md" in printed
    )
    built = next((tmp_path / "root").glob("dump-*/*"))
    assert (built / ".claude" / "skills" / "diagnose" / "SKILL.md").is_file()
    assert not list(built.parent.glob("*.claude-home")), "a dry run makes no cell"
