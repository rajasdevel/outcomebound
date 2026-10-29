"""Long eval driver, through fake CLI executables; no model calls."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from evals.harnesses.claude_code import ClaudeCodeHarness
from evals.harnesses.codex import CodexHarness
from evals.long_sessions import SessionError, next_message, read_session
from tests.eval_helpers import ROOT, RUN
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash
NAME = "session-synthetic"


def _kept_for_regrade(tmp_path, monkeypatch):
    fixtures = tmp_path / "engine/evals/fixtures"
    fixture = fixtures / NAME
    fixture.mkdir(parents=True)
    (fixture / "setup.sh").write_text(
        'set -eu\nmkdir -p "$1" "$2/checks"\n'
        'cp "$(dirname "$0")/probe.py" "$2/checks/probe.py"\n'
        'cd "$1"\nprintf "seed\\n" > kept.txt\ngit init -q\ngit add -A\n'
        "git -c user.name=Test -c user.email=test@example.invalid commit -qm seed\ngit tag seed\n",
        encoding="utf-8",
    )
    (fixture / "probe.py").write_text("print('observed: original grader')\n", encoding="utf-8")
    (fixture / "protected.paths").write_text("kept.txt\n", encoding="utf-8")
    (fixture / "prompt.md").write_text("Do the work.\n", encoding="utf-8")
    (fixture / "post.plan.json").write_text(
        json.dumps(
            {
                "version": 1,
                "claims": [
                    {
                        "name": "fix",
                        "kind": "static",
                        "risk": "wrong result",
                        "required": True,
                        "command": [
                            "sh",
                            "-c",
                            'python3 -I -B "$OUTCOMEBOUND_GRADER_DIR/checks/probe.py"',
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    RUN.set_harness("codex")
    workspace, stage, source = (tmp_path / name for name in ("workspace", "stage", "source"))
    for folder in (workspace, stage, source):
        folder.mkdir()
    arm = RUN.load_arm("none")
    failure, protected, seed, prompt = RUN.build_workspace(NAME, arm, workspace, {}, stage)
    assert failure is None
    sealed = source / f"{NAME}.graders"
    digest = RUN.seal(stage, fixture / "post.plan.json", fixtures.parent, NAME, sealed)
    for suffix, content in (
        ("answer.md", "Done."),
        ("prompt.md", prompt),
        ("transcript.txt", "{}"),
    ):
        (source / f"{NAME}.{suffix}").write_text(content, encoding="utf-8")
    meta = {
        **arm.record(),
        "fixture": NAME,
        "fixture_repo": str(workspace),
        "harness": "codex",
        "arm": "none",
        "model": "synthetic",
        "effort": "medium",
        "verdict": "PASS",
        "claims": {"fix": "PASS"},
        "error": None,
        "seed_sha": seed,
        "protected_snapshot": protected,
        "protected_intact": True,
        "workspace_sha256": RUN.workspace_digest(
            workspace, {**RUN.child_env(), **RUN.HERMETIC_GIT}
        ),
        "graders_sha256": digest,
        "grading_files_sha256": RUN.grading_digest(fixtures.parent, NAME),
    }
    (source / f"{NAME}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return fixtures.parent, meta, source


@pytest.mark.parametrize("kind", ["hard", "symbolic"])
@pytest.mark.parametrize("target", ["source", "stage"])
def test_setup_cannot_link_workspace_files_to_protected_inputs(tmp_path, monkeypatch, kind, target):
    """Catches setup leaving a content alias that a directory seal cannot protect."""
    evals, _meta, _source = _kept_for_regrade(tmp_path, monkeypatch)
    setup = evals / "fixtures" / NAME / "setup.sh"
    setup.write_text(
        setup.read_text(encoding="utf-8")
        + f"ln {'-s ' if kind == 'symbolic' else ''}"
        + ('"$(dirname "$0")/probe.py"' if target == "source" else '"$2/checks/probe.py"')
        + ' "$1/alias"\n',
        encoding="utf-8",
    )
    workspace, stage = tmp_path / "second-workspace", tmp_path / "second-stage"
    workspace.mkdir()
    stage.mkdir()
    extra: dict[str, Any] = {}
    failure, _protected, _seed, _prompt = RUN.build_workspace(
        NAME, RUN.load_arm("none"), workspace, extra, stage
    )
    assert failure is not None
    assert extra["void"] == "runner"
    assert (
        "setup linked " + ("fixture sources" if target == "source" else "grading stage") + ": alias"
        in extra["error"]
    )


def test_rescore_keeps_its_staged_grading_copy_unreadable(tmp_path, monkeypatch):
    """Catches rescore leaving a retained staged copy readable to a later call."""
    _evals, _meta, source = _kept_for_regrade(tmp_path, monkeypatch)
    assert RUN.rescore([source]) == 0
    (graders,) = source.glob("*.rescore-*.graders")
    assert graders.stat().st_mode & 0o7777 == 0
    assert RUN.rescore([source]) == 0
    assert graders.stat().st_mode & 0o7777 == 0


@pytest.mark.parametrize("sealed_copy", [False, True])
@pytest.mark.parametrize("origin", ["earlier_ref", "earlier_verbatim", "edits"])
def test_current_grader_regrade_keeps_historical_installs_and_grades_copies(
    tmp_path, monkeypatch, origin, sealed_copy
):
    """Catches rebuilding an old arm or grading in the original workspace or record."""
    evals, meta, source = _kept_for_regrade(tmp_path, monkeypatch)
    if sealed_copy:
        (source / f"{NAME}.graders").chmod(0)
    original_mode = (source / f"{NAME}.graders").stat().st_mode & 0o7777
    workspace = Path(meta["fixture_repo"])
    installed = workspace / ".agents/skills/helper/SKILL.md"
    installed.parent.mkdir(parents=True, exist_ok=True)
    installed.write_text("Historical guidance.\n", encoding="utf-8")
    meta.update(
        arm="comparison",
        arm_kind="earlier",
        arm_files={
            ".agents/skills/helper/SKILL.md": hashlib.sha256(installed.read_bytes()).hexdigest()
        },
        workspace_sha256=RUN.workspace_digest(workspace, {**RUN.child_env(), **RUN.HERMETIC_GIT}),
    )
    meta[origin] = {"sha256": "old-edits"} if origin == "edits" else "unavailable-history"
    actions = source / f"{NAME}.actions.json"
    actions.write_text('{"version":1,"actions":[]}\n', encoding="utf-8")
    meta["actions_file"] = str(actions)
    path = source / f"{NAME}.meta.json"
    path.write_text(json.dumps(meta), encoding="utf-8")
    probe = evals / "fixtures" / NAME / "probe.py"
    probe.write_text(
        "import os, subprocess\nfrom pathlib import Path\n"
        "assert Path('.agents/skills/helper/SKILL.md').read_text(encoding='utf-8') "
        "== 'Historical guidance.\\n'\n"
        "Path('kept.txt').write_text('changed by grading\\n', encoding='utf-8')\n"
        "subprocess.run(['git', 'add', 'kept.txt'], check=True)\n"
        "p=Path(os.environ['OB_ACTIONS'])\np.write_bytes(p.read_bytes()+b'\\n')\n"
        "print('observed: graded historical install on a copy')\n",
        encoding="utf-8",
    )

    def snapshot(root):
        return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    with RUN.grading_access(source / f"{NAME}.graders"):
        original_record, original_workspace = snapshot(source), snapshot(workspace)
    target = tmp_path / "current"
    assert RUN._main(["--regrade", str(source), "--out", str(target), "--current-graders"]) == 0
    again = json.loads((target / path.name).read_text(encoding="utf-8"))
    assert again["claims"]["fix"] == "PASS", again
    assert again["arm_files"] == meta["arm_files"] and again[origin] == meta[origin]
    assert again["current_graders"]["run_graders_sha256"] == meta["graders_sha256"]
    assert again["graders_sha256"] != meta["graders_sha256"]
    assert "observed: graded historical install on a copy" in again["observations"]
    with RUN.grading_access(source / f"{NAME}.graders"):
        assert snapshot(source) == original_record
    assert (source / f"{NAME}.graders").stat().st_mode & 0o7777 == original_mode
    assert (target / f"{NAME}.graders").stat().st_mode & 0o7777 == 0
    assert snapshot(workspace) == original_workspace
    assert Path(again["actions_file"]).parent == target
    assert not workspace.with_name(workspace.name + RUN.ASIDE).exists()


def test_current_grader_regrade_refuses_an_arm_file_that_differs_from_its_record(
    tmp_path, monkeypatch, capsys
):
    """Catches checking only workspace freshness while overlooking the arm's own digests."""
    _evals, meta, source = _kept_for_regrade(tmp_path, monkeypatch)
    workspace = Path(meta["fixture_repo"])
    meta.update(
        arm="comparison",
        arm_kind="earlier",
        earlier_ref="unavailable-history",
        arm_files={"kept.txt": "0" * 64},
    )
    assert (
        RUN.workspace_digest(workspace, {**RUN.child_env(), **RUN.HERMETIC_GIT})
        == meta["workspace_sha256"]
    )
    (source / f"{NAME}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    target = tmp_path / "refused"
    assert RUN._main(["--regrade", str(source), "--out", str(target), "--current-graders"]) == 2
    assert "arm's installed files differ from their recorded digests" in capsys.readouterr().err
    assert not target.exists()


@pytest.mark.parametrize("destination", ["record", "workspace"])
def test_regrade_refuses_to_write_output_inside_source_evidence(
    tmp_path, monkeypatch, capsys, destination
):
    """Catches an output directory modifying evidence before it is copied for grading."""
    _evals, meta, source = _kept_for_regrade(tmp_path, monkeypatch)
    root = source if destination == "record" else Path(meta["fixture_repo"])
    target = root / "new-record"
    assert RUN._main(["--regrade", str(source), "--out", str(target)]) == 2
    assert "outside the source record and kept workspaces" in capsys.readouterr().err
    assert not target.exists()


SESSION = {
    "shape": "interactive",
    "labels": ["opener", "info", "note", "nudge", "resume"],
    "max_turns": 6,
    "max_nudges": 2,
    "session_timeout_seconds": 30,
    "input_cap": 100000,
    "cut_after_calls": None,
    "cut_check": None,
    "resume_message": "Resume the work.",
    "next_turn": ["python3", "-I", "-B", "${OUTCOMEBOUND_GRADER_DIR}/checks/next.py"],
}
SETUP = r"""#!/bin/bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$1" "$2/checks"
cp "$here/next.py" "$here/scenario.json" "$here/check.py" "$here/cut.py" "$2/checks/"
cd "$1"
printf 'kept\n' > locked
printf 'Project notes.\n' > AGENTS.md
git init -q
git add -A
git -c user.name=Test -c user.email=test@example.invalid commit -qm seed
git tag seed
"""
NEXT = r"""import json, os, sys, time
from pathlib import Path

config = json.loads(Path(__file__).with_name("scenario.json").read_text(encoding="utf-8"))
turn = int(os.environ["OB_TURN"])
history = json.loads(Path(os.environ["OB_HISTORY"]).read_text(encoding="utf-8"))["turns"]
assert len(history) == turn
assert Path(os.environ["OB_LAST_ANSWER"]).read_text(encoding="utf-8") == f"Answer {turn}."
assert int(os.environ["OB_NUDGES"]) == sum(t["label"] == "nudge" for t in history)
assert Path(os.environ["OB_WORKSPACE"]).resolve() != Path.cwd().resolve()
if config.get("fault") == "crash":
    print("script failed deliberately", file=sys.stderr)
    sys.exit(7)
if config.get("fault") == "invalid":
    print('{"label":"invented","message":"go"}')
    sys.exit(0)
if config.get("delay"):
    time.sleep(config["delay"])
messages = config["messages"]
print(
    json.dumps(messages[turn - 1] if turn <= len(messages) else {"end": True, "reason": "complete"})
)
"""
CHECK = r"""import json, os
from pathlib import Path

turns = json.loads(Path(os.environ["OB_TURNS"]).read_text(encoding="utf-8"))["turns"]
assert turns and all(t["calls"] >= 1 for t in turns)
for i, turn in enumerate(turns, 1):
    assert Path(turn["answer_path"]).is_file()
    assert f"--- turn {i}: {turn['label']} ---" in Path(turn["transcript"]).read_text(
        encoding="utf-8"
    )
    assert turn["started_at"] <= turn["ended_at"]
assert Path("locked").read_text(encoding="utf-8") == "kept\n"
assert not Path("graded").exists(), "post-checks ran more than once"
Path("graded").write_text("once", encoding="utf-8")
print("observed: turns kept")
"""
FAKE = r"""#!/usr/bin/env python3
import json, os, signal, sys, time
from pathlib import Path

argv = sys.argv[1:]


def opt(name):
    return argv[argv.index(name) + 1] if name in argv else None


log = Path(os.environ["FAKE_LOG"])
previous = (
    [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
)
turn = len(previous) + 1
claude = Path(sys.argv[0]).name == "claude"
resumed = opt("--resume") if claude else (argv[-2] if "resume" in argv else None)
key = resumed or f"11111111-1111-4111-8111-{turn:012d}"
message = sys.stdin.read()
with log.open("a", encoding="utf-8") as out:
    out.write(
        json.dumps(
            {
                "argv": argv,
                "prompt": message,
                "session": key,
                "home": os.environ.get("HOME"),
                "config": os.environ.get("CLAUDE_CONFIG_DIR"),
                "root_modes": [(Path.cwd().parent).stat().st_mode & 0o7777,
                               log.parent.stat().st_mode & 0o7777,
                               (log.parent / "out").stat().st_mode & 0o7777],
            }
        )
        + "\n"
    )
cwd = os.getcwd()
model = opt("--model") if claude else opt("-m")
if turn == 2 and os.environ.get("FAKE_WRONG_SECOND"):
    model = "wrong-model"
effort = (
    opt("--effort")
    if claude
    else next(a.split("=", 1)[1] for a in argv if a.startswith("model_reasoning_effort="))
)
if claude:
    folder = Path(os.environ["CLAUDE_CONFIG_DIR"], "projects", "fixture")
    source = folder / f"{key}.jsonl"
else:
    folder = Path(os.environ["CODEX_HOME"], "sessions", "2026", "10", "27")
    part = "02" if turn >= 2 and os.environ.get("FAKE_TWO_FILES") else "01"
    source = folder / f"rollout-2026-10-27T00-00-{part}-{key}.jsonl"
folder.mkdir(parents=True, exist_ok=True)
rows = (
    [json.loads(l) for l in source.read_text(encoding="utf-8").splitlines()]
    if source.exists()
    else []
)
handle = source.open("a", encoding="utf-8")


def native(row):
    if claude:
        row["sessionId"] = key
    handle.write(json.dumps(row) + "\n")
    handle.flush()


def emit(row):
    print(json.dumps({**row, **({"session_id": key} if claude else {})}), flush=True)


if claude:
    home = Path(os.environ["HOME"], "turn-marker")
    config = Path(os.environ["CLAUDE_CONFIG_DIR"], "turn-marker")
    if turn > 1:
        assert home.read_text(encoding="utf-8") == str(turn - 1)
        assert config.read_text(encoding="utf-8") == str(turn - 1)
    home.write_text(str(turn), encoding="utf-8")
    config.write_text(str(turn), encoding="utf-8")
    native({"type": "user", "cwd": cwd, "message": {"role": "user", "content": message}})
    native(
        {
            "type": "attachment",
            "cwd": cwd,
            "attachment": {
                "type": "instructions",
                "files": [{"path": str(Path(cwd, "AGENTS.md")), "type": "Project", "content": ""}],
            },
        }
    )
    native(
        {
            "type": "attachment",
            "cwd": cwd,
            "attachment": {"type": "skill_listing", "names": [], "skillCount": 0},
        }
    )
    emit(
        {
            "type": "system",
            "subtype": "init",
            "cwd": cwd,
            "model": model,
            "permissionMode": "acceptEdits",
            "apiKeySource": "none",
            "claude_code_version": "2.1.999",
            "tools": ["Bash", "Read", "Edit", "Write"],
            "mcp_servers": [],
            "skills": [],
            "plugins": [],
        }
    )
else:
    if not rows:
        native(
            {"type": "session_meta", "payload": {"id": key, "cwd": cwd, "cli_version": "0.164.0"}}
        )
    native(
        {
            "type": "turn_context",
            "payload": {
                "cwd": cwd,
                "model": model,
                "effort": effort,
                "sandbox_policy": {
                    "type": "workspace-write",
                    "network_access": False,
                    "writable_roots": [],
                },
            },
        }
    )
    emit({"type": "thread.started", "thread_id": key})
    emit({"type": "turn.started"})
if os.environ.get("FAKE_SPLIT") and turn == int(os.environ.get("FAKE_SPLIT_TURN", "1")):

    def interrupted(sig, _frame):
        with Path(os.environ["FAKE_SIGNAL"]).open("a", encoding="utf-8") as log:
            log.write(str(sig) + "\n")
        if not os.environ.get("FAKE_STUBBORN"):
            sys.exit(0)

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)

usage = {
    "input_tokens": 200,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 800,
    "output_tokens": 50,
}
if claude:
    msg = {
        "id": f"msg-{turn}",
        "role": "assistant",
        "model": model,
        "usage": usage,
        "content": [{"type": "text", "text": f"Answer {turn}."}],
    }
    native({"type": "assistant", "cwd": cwd, "effort": effort, "message": msg})
    emit({"type": "assistant", "message": msg, "parent_tool_use_id": None})
else:
    prior = [
        r["payload"]["info"]["total_token_usage"]
        for r in rows
        if r.get("type") == "event_msg"
        and r.get("payload", {}).get("type") == "token_count"
        and r["payload"].get("info")
    ]
    n = turn if resumed else 1
    native(
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {
                        "input_tokens": 1000,
                        "cached_input_tokens": 800,
                        "output_tokens": 50,
                        "reasoning_output_tokens": 20,
                    },
                    "total_token_usage": {
                        "input_tokens": 1000 * n,
                        "cached_input_tokens": 800 * n,
                        "output_tokens": 50 * n,
                        "reasoning_output_tokens": 20 * n,
                    }
                },
            },
        }
    )
    # A count without info is not a model call.
    native({"type": "event_msg", "payload": {"type": "token_count", "info": None}})
    Path(opt("--output-last-message")).write_text(f"Answer {turn}.", encoding="utf-8")
if os.environ.get("FAKE_SPLIT") and turn == int(os.environ.get("FAKE_SPLIT_TURN", "1")):
    if not os.environ.get("FAKE_NO_CHECKPOINT"):
        Path("checkpoint").write_text("reached", encoding="utf-8")
    time.sleep(60)
if os.environ.get("FAKE_SLOW"):
    time.sleep(60)
if claude:
    emit(
        {
            "type": "result",
            "subtype": "success",
            "result": f"Answer {turn}.",
            "is_error": False,
            "num_turns": 1,
            "usage": usage,
            "permission_denials": [],
            "total_cost_usd": 0.01,
        }
    )
else:
    emit(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1000,
                "cached_input_tokens": 800,
                "output_tokens": 50,
                "reasoning_output_tokens": 20,
            },
        }
    )
"""


@pytest.fixture
def trusted() -> Any:
    base = ROOT / ".agents" / "work" / "eval-native-tests"
    base.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="session-", dir=base))
    yield folder
    RUN._remove_copy(folder)


def _fixture(tmp_path: Path, session: dict[str, Any], scenario: dict[str, Any]) -> Path:
    fixture = tmp_path / "fixtures" / NAME
    fixture.mkdir(parents=True)
    for name, text in (
        ("setup.sh", SETUP),
        ("prompt.md", "Do the work."),
        ("next.py", NEXT),
        ("check.py", CHECK),
        (
            "cut.py",
            "import os,sys\nfrom pathlib import Path\n"
            'sys.exit(0 if Path(os.environ["OB_WORKSPACE"], "checkpoint").exists() else 1)\n',
        ),
        ("protected.paths", "locked\n"),
    ):
        (fixture / name).write_text(text, encoding="utf-8")
    (fixture / "session.json").write_text(json.dumps(session), encoding="utf-8")
    (fixture / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
    plan = {
        "version": 1,
        "cwd": ".",
        "claims": [
            {
                "name": "turns",
                "risk": "turn record lost",
                "kind": "static",
                "required": True,
                "command": [
                    "sh",
                    "-c",
                    'exec python3 -I -B "$OUTCOMEBOUND_GRADER_DIR/checks/check.py"',
                ],
            }
        ],
    }
    (fixture / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return fixture.parent


def _run(
    tmp_path: Path,
    trusted: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: str = "codex",
    session: dict[str, Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    scenario: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    fixtures = _fixture(
        tmp_path,
        {**SESSION, **(session or {})},
        {
            "messages": messages
            if messages is not None
            else [
                {"label": "info", "message": "More facts."},
                {"label": "note", "message": "Write a note."},
            ],
            **(scenario or {}),
        },
    )
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for cli in ("codex", "claude"):
        executable = bindir / cli
        executable.write_text(FAKE, encoding="utf-8")
        executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_LOG", str(trusted / "calls.jsonl"))
    monkeypatch.setenv("CODEX_HOME", str(trusted / "codex"))
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    tool = (ClaudeCodeHarness if harness == "claude-code" else CodexHarness)(
        RUN.child_env, RUN._run
    )
    out = trusted / "out"
    out.mkdir()
    status = {
        "model": "test-model",
        "effort": "medium",
        "repetition": 1,
        "workspace_root": str(tmp_path / "workspaces"),
        "harness": harness,
        "arm": "none",
    }
    failed, _row = RUN.run_one(out, status, NAME, RUN.load_arm("none"), os.environ["PATH"], tool)
    meta = json.loads((out / f"{NAME}.meta.json").read_text(encoding="utf-8"))
    calls = [
        json.loads(line)
        for line in (trusted / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert failed == bool(meta["error"])
    return meta, calls, out


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_three_turns_resume_and_keep_answers_native_copies_and_one_final_grade(
    tmp_path, trusted, monkeypatch, harness
):
    """Catches fresh sessions, lost artifacts, duplicate costs and grading each turn."""
    meta, calls, out = _run(tmp_path, trusted, monkeypatch, harness, scenario={"delay": 0.1})
    assert meta["error"] == "", meta
    assert meta["verdict"] == "PASS" and meta["claims"] == {"turns": "PASS"}
    assert len(calls) == 3 and len({c["session"] for c in calls}) == 1
    assert all(call["root_modes"] == [0o311, 0o311, 0o311] for call in calls)
    assert trusted.stat().st_mode & 0o7777 == 0o700
    assert calls[1]["prompt"] == "More facts." and calls[2]["prompt"] == "Write a note."
    assert ("--resume" if harness == "claude-code" else "resume") in calls[1]["argv"]
    if harness == "codex":
        assert calls[1]["argv"][:2] == ["exec", "resume"] and calls[1]["argv"][-1] == "-"
        assert all(flag not in calls[1]["argv"] for flag in ("-C", "-s", "--add-dir"))
    else:
        assert len({c["home"] for c in calls}) == len({c["config"] for c in calls}) == 1
        assert meta["isolation_verdict"] == "UNVERIFIED"
        assert "root-permissions" in meta["isolation_unverified"]
    turns = json.loads(Path(meta["turns_file"]).read_text(encoding="utf-8"))["turns"]
    assert [t["label"] for t in turns] == ["opener", "info", "note"]
    assert [t["calls"] for t in turns] == [1, 1, 1]
    assert [t["session_tokens"]["input_tokens"] for t in turns] == [1000, 1000, 1000]
    assert meta["session_tokens"]["input_tokens"] == 3000
    assert meta["session_tokens"]["cached_input_tokens"] == 2400
    assert meta["session_tokens"]["output_tokens"] == 150
    assert meta["elapsed_seconds"] - meta["active_seconds"] >= 0.2
    assert len(meta["native_sessions"]) == 1
    assert len(list(out.glob("*.native.jsonl"))) == 3
    transcript = json.loads(
        (out / f"{NAME}.transcript.txt")
        .read_text(encoding="utf-8")
        .split("\n--- post-checks ---", 1)[0]
    )
    assert [t["turn"] for t in transcript["turns"]] == [1, 2, 3]
    assert "--- turn 3: note ---" in transcript["stdout"]
    assert RUN.kept_records(meta).turns == Path(meta["turns_file"])
    plan: dict[str, Any] = {}
    assert RUN._regrade_files(out / f"{NAME}.meta.json", NAME, meta, plan) == ""
    kept, _answer, _filled = RUN.kept_transcript(plan, meta)
    assert json.loads(kept)["turns"] == transcript["turns"]


def test_resume_counts_two_native_files_once(tmp_path, trusted, monkeypatch):
    """Catches adding cumulative snapshots or refusing a second rollout for the same thread."""
    meta, _calls, _out = _run(tmp_path, trusted, monkeypatch, env={"FAKE_TWO_FILES": "1"})
    assert meta["error"] == "", meta
    assert meta["verdict"] == "PASS" and len(meta["native_sessions"]) == 2
    assert meta["session_tokens"]["input_tokens"] == 3000
    assert [t["input_tokens"] for t in meta["turn_tokens"]] == [1000, 1000, 1000]


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_nudge_is_resumed_and_the_cap_is_enforced(tmp_path, trusted, monkeypatch, harness):
    """Catches nudges lost from history or sent after max_nudges."""
    meta, calls, _out = _run(
        tmp_path,
        trusted,
        monkeypatch,
        harness,
        session={"shape": "unattended", "max_nudges": 1},
        messages=[{"label": "nudge", "message": "Continue."}] * 2,
    )
    assert meta["error"] == "", meta
    assert len(calls) == 2 and calls[1]["prompt"] == "Continue."
    assert meta["nudges"] == 1 and meta["budget"]["stopped"] == "max_nudges"
    assert meta["verdict"] == "FAIL" and meta["checks_verdict"] == "PASS"


def test_max_turns_is_graded_as_failure_without_another_call(tmp_path, trusted, monkeypatch):
    meta, calls, _out = _run(tmp_path, trusted, monkeypatch, session={"max_turns": 2})
    assert meta["error"] == "", meta
    assert len(calls) == 2 and meta["budget"]["stopped"] == "max_turns"
    assert meta["verdict"] == "FAIL" and meta["checks_verdict"] == "PASS"


@pytest.mark.parametrize("fault", ["crash", "invalid"])
def test_next_turn_fault_voids_the_run_and_keeps_its_stderr(tmp_path, trusted, monkeypatch, fault):
    meta, calls, out = _run(tmp_path, trusted, monkeypatch, scenario={"fault": fault})
    assert len(calls) == 1 and meta["void"] == "runner" and meta["verdict"] == "UNVERIFIED"
    assert "next_turn" in meta["error"] and meta["budget"]["stopped"] is None
    if fault == "crash":
        assert "exited 7" in meta["error"]
        assert (out / f"{NAME}.next-1.stderr.txt").read_text(
            encoding="utf-8"
        ) == "script failed deliberately\n"
    else:
        assert "is not declared" in meta["error"]
        assert "invented" in (out / f"{NAME}.next-1.stdout.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_split_interrupts_the_first_call_and_starts_a_new_session(
    tmp_path, trusted, monkeypatch, harness
):
    """Catches counting null-info events, resuming the cut thread, or losing its usage."""
    signal_file = trusted / "signal"
    meta, calls, _out = _run(
        tmp_path,
        trusted,
        monkeypatch,
        harness,
        session={
            "shape": "split",
            "cut_after_calls": 20,
            "cut_check": ["python3", "${OUTCOMEBOUND_GRADER_DIR}/checks/cut.py"],
        },
        messages=[{"end": True, "reason": "done"}],
        env={"FAKE_SPLIT": "1", "FAKE_SIGNAL": str(signal_file)},
    )
    assert not signal_file.exists()
    state = json.loads(Path(meta["cut_state"]).read_text(encoding="utf-8"))
    assert state["processes_stopped"] and "seed" in state["git_log"]
    assert (
        state["files"]["checkpoint"]["sha256"]
        == "52774637822c236d84ed1e221bb24d9c1840e08c9d3542efd26f16e27ac8c0a2"
    )
    assert "?? checkpoint" in state["git_status"]
    assert meta["error"] == "", meta
    assert meta["verdict"] == "PASS" and len(calls) == 2
    assert meta["split_boundary"] == "cut" and meta["split_reached"] is True
    assert calls[0]["session"] != calls[1]["session"]
    assert calls[1]["prompt"] == "Resume the work."
    assert "resume" not in calls[1]["argv"] and "--resume" not in calls[1]["argv"]
    assert [t["label"] for t in meta["turns"]] == ["opener", "resume"]
    assert len(meta["native_sessions"]) == 2
    assert meta["session_tokens"]["input_tokens"] == 2000


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_cumulative_input_cap_is_not_reset_on_resume(tmp_path, trusted, monkeypatch, harness):
    meta, calls, _out = _run(tmp_path, trusted, monkeypatch, harness, session={"input_cap": 2000})
    assert meta["error"] == "", meta
    assert len(calls) == 2 and meta["budget"]["stopped"] == "input_cap"
    assert meta["verdict"] == "FAIL" and meta["session_tokens"]["input_tokens"] == 2000


def test_session_timeout_includes_next_turn_time(tmp_path, trusted, monkeypatch):
    meta, calls, _out = _run(
        tmp_path,
        trusted,
        monkeypatch,
        session={"session_timeout_seconds": 1},
        scenario={"delay": 2},
    )
    assert len(calls) == 1
    assert meta["error"] == "", meta
    assert meta["budget"]["stopped"] == "timeout" and meta["verdict"] == "FAIL"


def test_session_files_and_session_prefix_are_named_only(tmp_path, monkeypatch):
    fixtures = _fixture(tmp_path, SESSION, {"messages": []})
    shutil.copytree(fixtures / NAME, fixtures / "plain-session")
    (fixtures / "short").mkdir()
    (fixtures / "short" / "setup.sh").write_text("true\n", encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    assert RUN.fixture_names() == sorted([NAME, "plain-session", "short"])
    assert RUN.default_fixtures() == ["short"]
    assert "session-unknown".startswith(RUN.NAMED_ONLY)
    assert not "long-run".startswith(RUN.NAMED_ONLY)


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"shape": "other"}, "shape"),
        ({"labels": []}, "labels"),
        ({"labels": ["Opener"]}, "label"),
        ({"labels": ["opener", "opener"]}, "distinct"),
        ({"unknown": 1}, "unknown fields"),
        ({"max_turns": True}, "max_turns"),
        ({"max_turns": 0}, "max_turns"),
        ({"max_nudges": -1}, "max_nudges"),
        ({"max_nudges": False}, "max_nudges"),
        ({"input_cap": 0}, "input_cap"),
        ({"input_cap": 1.5}, "input_cap"),
        ({"session_timeout_seconds": False}, "session_timeout_seconds"),
        ({"session_timeout_seconds": float("nan")}, "session_timeout_seconds"),
        ({"session_timeout_seconds": float("inf")}, "session_timeout_seconds"),
        ({"next_turn": []}, "next_turn"),
        ({"next_turn": "python3"}, "next_turn"),
        ({"next_turn": ["python3", "\0"]}, "next_turn"),
        ({"cut_after_calls": 1}, "only to split"),
        ({"shape": "split"}, "cut_check"),
        ({"shape": "split", "cut_after_calls": True}, "cut_after_calls"),
        ({"shape": "split", "cut_check": ["script"], "resume_message": ""}, "resume_message"),
        ({"shape": "split", "cut_check": ["script"], "max_turns": 1}, "max_turns"),
        ({"resume_message": None}, "resume_message"),
    ],
)
def test_invalid_session_is_refused_before_setup(tmp_path, monkeypatch, change, error):
    fixtures = _fixture(tmp_path, {**SESSION, **change}, {"messages": []})
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    with pytest.raises(SessionError, match=error):
        read_session(fixtures / NAME / "session.json")
    assert error in RUN.suite_refusal(NAME)
    with pytest.raises(SystemExit) as refused:
        RUN.checked_fixtures(
            RUN._parser(),
            RUN._parser().parse_args(
                ["--arm", "none", "--model", "test-model", "--fixtures", NAME]
            ),
        )
    assert refused.value.code == 2


@pytest.mark.parametrize("raw", ["[]", "{", '{"shape":"interactive","shape":"split"}', "{}"])
def test_unreadable_or_incomplete_session_is_refused(tmp_path, raw):
    path = tmp_path / "session.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(SessionError):
        read_session(path)


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '{"end":false,"reason":"x"}',
        '{"end":true}',
        '{"label":"nudge","message":""}',
        '{"label":"info","message":"go","extra":1}',
        '{"label":"info","message":"a","message":"b"}',
    ],
)
def test_next_turn_output_is_strict(raw):
    with pytest.raises(SessionError):
        next_message(raw, ("info", "nudge"))


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_running_call_stops_at_the_input_cap(tmp_path, trusted, monkeypatch, harness):
    """Catches checking a cap only after an unbounded harness returns."""
    meta, calls, _out = _run(
        tmp_path, trusted, monkeypatch, harness, session={"input_cap": 500}, env={"FAKE_SLOW": "1"}
    )
    assert meta["error"] == "", meta
    assert len(calls) == 1 and meta["budget"]["stopped"] == "input_cap"
    assert meta["verdict"] == "FAIL" and meta["session_tokens"]["input_tokens"] == 1000


def test_split_safety_stop_is_a_graded_budget_stop_without_restart(tmp_path, trusted, monkeypatch):
    """Catches voiding a first session that never reaches its checkpoint, which would drop the
    runs that fail to deliver from the comparison."""
    meta, calls, _out = _run(
        tmp_path,
        trusted,
        monkeypatch,
        session={
            "shape": "split",
            "cut_after_calls": 1,
            "cut_check": ["python3", "${OUTCOMEBOUND_GRADER_DIR}/checks/cut.py"],
        },
        messages=[],
        env={"FAKE_SPLIT": "1", "FAKE_NO_CHECKPOINT": "1"},
    )
    assert len(calls) == 1 and not meta.get("void") and not meta["error"]
    assert meta["split_reached"] is False and meta["budget"]["stopped"] == "cut_after_calls"
    assert meta["verdict"] == "FAIL"


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_resumed_identity_is_checked_before_sending_more_turns(
    tmp_path, trusted, monkeypatch, harness
):
    """Catches checking only the first session's model identity."""
    meta, calls, _out = _run(
        tmp_path, trusted, monkeypatch, harness, env={"FAKE_WRONG_SECOND": "1"}
    )
    assert meta["error"] and len(calls) == 2
    assert any(row[0] == "native-model" and row[1] == "FAIL" for row in meta["identity_checks"])


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_split_counts_the_first_session_across_an_early_stop_and_nudge(
    tmp_path, trusted, monkeypatch, harness
):
    """Catches resetting the split threshold when the first native session is resumed."""
    signal_file = trusted / "signal"
    meta, calls, _out = _run(
        tmp_path,
        trusted,
        monkeypatch,
        harness,
        session={
            "shape": "split",
            "cut_after_calls": 20,
            "cut_check": ["python3", "${OUTCOMEBOUND_GRADER_DIR}/checks/cut.py"],
        },
        messages=[{"label": "nudge", "message": "Continue."}],
        env={"FAKE_SPLIT": "1", "FAKE_SPLIT_TURN": "2", "FAKE_SIGNAL": str(signal_file)},
    )
    assert meta["error"] == "", meta
    assert meta["verdict"] == "PASS" and len(calls) == 3
    assert calls[0]["session"] == calls[1]["session"] != calls[2]["session"]
    assert [t["label"] for t in meta["turns"]] == ["opener", "nudge", "resume"]
    assert meta["session_tokens"]["input_tokens"] == 3000


@pytest.mark.skipif(os.name == "nt", reason="POSIX folder modes")
def test_a_graded_copy_with_an_unreadable_folder_is_removed_whole(tmp_path):
    copy = tmp_path / "out" / "session-synthetic.graders"
    locked = copy / "checks"
    locked.mkdir(parents=True)
    (locked / "check.py").write_text("x", encoding="utf-8")
    os.chmod(locked, 0)
    try:
        RUN._remove_copy(tmp_path / "out")
    finally:
        if locked.exists():
            os.chmod(locked, 0o700)
    assert not (tmp_path / "out").exists()
