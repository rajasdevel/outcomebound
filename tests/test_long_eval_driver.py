"""Driver protocol and contamination regressions, with synthetic native records only."""

from __future__ import annotations

import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from evals import long_sessions
from evals import session_protocol as P
from evals.harnesses import Request
from evals.long_sessions import Driver, Driving, next_message, read_session
from evals.session_evidence import ActionLedger, contamination, decode_native, family_evidence
from evals.session_permissions import sealed_roots
from evals.session_shell import command_segments
from evals.watch import watched_command
from tests.eval_helpers import ROOT, RUN, load
from tests.portable import needs_posix_bash
from tests.test_long_eval_protocol import FakeHarness, _count, _driver, _meta, _rows


@pytest.fixture
def isolated_invocation_sources(tmp_path, monkeypatch):
    sources = tmp_path.resolve() / "source/evals/fixtures"
    for name in (
        "session-resume/install.json",
        "session-feature-day/install.json",
        "brief-runbook/install.json",
        "session/corelib/reference.py",
        "brief/plant.py",
    ):
        target = sources / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RUN.FIXTURES / name, target)
    monkeypatch.setattr(RUN, "FIXTURES", sources)
    return sources


WORKSPACE_COMMANDS = [
    "pwd; git status --short; rg --files -g 'AGENTS.md' -g '*route*' -g 'Makefile'",
    "cat docs/{a,b}.md; cat CHANGELOG.md; git remote -v",
    "cat > package/policy.py <<'EOF'\nvalue = {'paths': ['$INPUT', '../other/answer.txt']}\nEOF\n",
    "cat >> tests/test_policy.py <<'EOF'\nassert value == {'a': 1}\nEOF\npython3 -m unittest",
    "cat > package/readiness.py <<'EOF'\nfrom package.policy import value\nEOF",
    "cat >> tests/test_policy.py <<'EOF'\nassert {'a', 'b'} == set(value)\nEOF\ngit status --short",
    "cat >> tests/test_policy.py <<'EOF'\n# data: $(cat ../other/answer.txt)\nEOF\nfalse",
    "cat >> tests/test_policy.py <<'EOF'\nassert True\nEOF\ncat docs/*.md",
    (
        "python3 - <<'PY'\nfrom pathlib import Path\n"
        "p = Path('package/app.py')\np.write_text(p.read_text().replace('before', 'after'))\n"
        "PY\ncat > docs/note.md <<'EOF'\n# Note\nEOF\nmake docs-check"
    ),
    (
        "python3 - <<'PY'\nfrom pathlib import Path\n"
        "print(Path('data/feedback.jsonl').read_text())\nPY\npython3 -m unittest"
    ),
    (
        "cat > docs/testing.md <<'EOF'\n# Checks\nEOF\npython3 - <<'PY'\n"
        "from pathlib import Path\nPath('CHANGELOG.md').write_text('Updated')\nPY\ngit diff --check"
    ),
    (
        "python3 - <<'PY'\nfrom pathlib import Path\n"
        "for name in ('docs/a.md', 'docs/b.md'):\n    p = Path(name)\n"
        "    p.write_text(p.read_text())\nPY\nmake docs-check"
    ),
    (
        "python3 - <<'PY'\nfrom pathlib import Path\n"
        "Path('docs/a.md').write_text('Done')\nPY\ngit status --short"
    ),
    (
        "cat docs/{a,b}.md; python3 - <<'PY'\nfrom pathlib import Path\n"
        "print(Path('data/feedback.jsonl').read_text())\nPY"
    ),
    "cat > status-note.md <<'EOF'\n# Status\nEOF\ngit diff --check",
]


@needs_posix_bash
def test_checkpoint_commit_at_natural_exit_starts_fresh_without_a_nudge(tmp_path):
    """Catches a third ticket commit between polls being followed by a nudge."""
    driver, harness = _driver(tmp_path, [{"label": "nudge", "message": "Continue."}], shape="split")
    workspace = driver.place.workspace
    for args in (
        ["init", "-q"],
        ["config", "user.name", "Test"],
        ["config", "user.email", "test@example.invalid"],
        ["commit", "--allow-empty", "-qm", "seed"],
        ["tag", "seed"],
        ["commit", "--allow-empty", "-qm", "ticket 021: done"],
        ["commit", "--allow-empty", "-qm", "ticket 022: done"],
    ):
        subprocess.run(["git", *args], cwd=workspace, check=True, capture_output=True)
    program = driver.place.stage / "cut.py"
    program.write_bytes((ROOT / "evals/fixtures/session/corelib/checks/cut_check.py").read_bytes())
    driver.session = driver.session._replace(cut_check=(sys.executable, str(program)))
    original = harness.call

    def call(*args):
        if not harness.requests:
            assert driver.cut_check() is None
            done = watched_command(
                ["git", "commit", "--allow-empty", "-qm", "ticket 023: held"],
                cwd=workspace,
                timeout=5,
                poll=lambda _: driver.cut_check(),
            )
            assert done.returncode == 0 and done.stopped is None
            assert driver.cut_polls == 1
        return original(*args)

    harness.call = call
    result = driver.call(driver.base)
    assert driver.following(result)
    assert driver.pending["label"] == "resume"
    assert driver.nudges == 0 and driver.resumed == ""
    assert driver.extras["split_boundary"] == "natural"
    assert driver.cut_polls == 2
    state = json.loads(Path(driver.extras["cut_state"]).read_text(encoding="utf-8"))
    assert "ticket 023: held" in state["git_log"]
    assert state["processes_stopped"] is False
    driver.call(driver.base)
    assert len(harness.requests) == 2 and harness.requests[-1].resume == ""
    assert [turn["session_id"] for turn in driver.turns] == ["session-1", "session-2"]


def _executed_command(command, workspace, key="command", code=0):
    return {
        "type": "event_msg",
        "payload": {
            "type": "item_completed",
            "item": {
                "type": "CommandExecution",
                "id": key,
                "command": command,
                "cwd": str(workspace),
                "exit_code": code,
            },
        },
    }


@pytest.mark.parametrize("completion", [None, 0, 7])
def test_cut_exec_requests_reach_actions_once_and_take_only_native_results(tmp_path, completion):
    """Catches a cut wrapper losing its command, or a result duplicating its request."""
    command = (
        "git commit -m 'finish work'; GIT_TERMINAL_PROMPT=0 git push origin HEAD:refs/heads/main"
    )
    driver, harness = _driver(tmp_path, [], stops=("timeout",))
    request = {
        "type": "response_item",
        "timestamp": "2026-01-01T00:00:00Z",
        "payload": {
            "type": "custom_tool_call",
            "name": "exec",
            "call_id": "wrapper",
            "input": "text(await tools.exec_command({cmd:"
            + json.dumps(command)
            + ', workdir:"."}));',
        },
    }
    harness.rows["session-1"] = [_meta("session-1"), request]
    driver.call(driver.base)
    actions = P.actions(json.loads(driver.actions_file.read_text(encoding="utf-8")))
    commands = [a for a in actions if a["kind"] == "command"]
    assert [(a["command"], a["status"], a["exit_code"]) for a in commands] == [
        (command, "unknown", None)
    ]
    assert commands[0]["cwd"] == str(driver.place.workspace)
    assert commands[0]["started_at"] == "2026-01-01T00:00:00Z"
    rows = harness.rows["session-1"]
    if completion is not None:
        rows.append(_executed_command(command, driver.place.workspace, code=completion))
    item = _rows(tmp_path / "later.jsonl", rows)
    assert driver.actions.add([item], "codex", driver.place.workspace) == []
    driver.write_records()
    commands = [
        a
        for a in P.actions(json.loads(driver.actions_file.read_text(encoding="utf-8")))
        if a["kind"] == "command"
    ]
    expected = "unknown" if completion is None else "ok" if completion == 0 else "failed"
    assert [(a["command"], a["status"], a["exit_code"]) for a in commands] == [
        (command, expected, completion)
    ]


@pytest.mark.parametrize("completion", [None, 0, 7])
def test_cut_native_command_start_is_kept_without_a_completion(tmp_path, completion):
    """Catches a native start being dropped when no function request was retained."""
    started = _executed_command("git push origin main", tmp_path, code=None)
    started["payload"]["type"] = "item_started"
    rows = [_meta("session"), started]
    if completion is not None:
        rows.append(_executed_command("git push origin main", tmp_path, code=completion))
    item = _rows(tmp_path / "cut.jsonl", rows)
    (action,) = ActionLedger().add([item], "codex", tmp_path)
    P.action(action)
    assert (action["command"], action["status"], action["exit_code"]) == (
        "git push origin main",
        "unknown" if completion is None else "ok" if completion == 0 else "failed",
        completion,
    )


def test_exec_wrapper_keeps_unfinished_siblings_and_ignores_quoted_calls(tmp_path):
    """Catches one completed nested request hiding an unfinished sibling or quoted data."""
    wrapper = {
        "type": "response_item",
        "payload": {
            "type": "custom_tool_call",
            "name": "exec",
            "call_id": "batch",
            "input": (
                """const sample = "tools.exec_command({cmd: 'git push fake'})";\n"""
                '// tools.exec_command({cmd:"git push commented"})\n'
                "text(await tools.exec_command({cmd:'git status --short'}));\n"
                "text(await tools.exec_command({cmd:`git push origin main`}));\n"
            ),
        },
    }
    done = _executed_command("git status --short", tmp_path)
    item = _rows(tmp_path / "batch.jsonl", [_meta("session"), wrapper, done])
    actions = ActionLedger().add([item], "codex", tmp_path)
    assert [(a["command"], a["status"]) for a in actions if a["kind"] == "command"] == [
        ("git status --short", "ok"),
        ("git push origin main", "unknown"),
    ]


def test_completed_file_edit_does_not_hide_another_edit_cut_before_its_result(tmp_path):
    """Catches blanket suppression of patch requests when any native file change exists."""
    rows = [_meta("session")]
    rows[0]["payload"]["cwd"] = str(tmp_path)
    for name in ("finished.py", "unfinished.py"):
        rows.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "apply_patch",
                    "call_id": name,
                    "input": f"*** Begin Patch\n*** Add File: {name}\n+text\n*** End Patch",
                },
            }
        )
        if name == "finished.py":
            rows.append(
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "item_completed",
                        "item": {
                            "type": "FileChange",
                            "id": "change",
                            "status": "completed",
                            "changes": [{"kind": "add", "path": str(tmp_path / name)}],
                        },
                    },
                }
            )
    item = _rows(tmp_path / "patches.jsonl", rows)
    actions = ActionLedger().add([item], "codex", tmp_path)
    assert [(a["paths"], a["status"]) for a in actions] == [
        ([str(tmp_path / "finished.py")], "ok"),
        ([str(tmp_path / "unfinished.py")], "unknown"),
    ]


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_command_actions_record_literal_inline_effects_on_both_harnesses(tmp_path, harness):
    """Catches graders receiving unresolved edit scripts or mistaking their data for runs."""
    command = (
        "cd package && python3 - <<'PY' && cat > note.md <<'EOF'\nfrom pathlib import Path\n"
        "for name in ('a.py', 'b.py'):\n"
        "    p = Path(name)\n    p.write_text(p.read_text().replace('old', 'new'))\n"
        "PY\nsubprocess.run(['git', 'push'])\nEOF"
    )
    if harness == "codex":
        rows = [_executed_command(command, tmp_path)]
    else:
        rows = [
            {
                "type": "assistant",
                "cwd": str(tmp_path),
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "id": "edit",
                            "input": {"command": command},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "edit",
                            "is_error": False,
                            "content": "",
                        }
                    ]
                },
            },
        ]
    item = _rows(tmp_path / "native.jsonl", rows)
    (action,) = ActionLedger().add([item], harness, tmp_path, "session")
    P.action(action)
    assert action["segments"] == [
        {
            "argv": ["cd", "package"],
            "cwd": str(tmp_path),
            "status": "ok",
            "reads": [str(tmp_path / "package")],
            "writes": [],
            "runs": [],
        },
        {
            "argv": ["python3", "-"],
            "cwd": str(tmp_path / "package"),
            "status": "ok",
            "reads": [str(tmp_path / "package/a.py"), str(tmp_path / "package/b.py")],
            "writes": [str(tmp_path / "package/a.py"), str(tmp_path / "package/b.py")],
            "runs": [],
        },
        {
            "argv": ["cat"],
            "cwd": str(tmp_path / "package"),
            "status": "ok",
            "reads": [],
            "writes": [str(tmp_path / "package/note.md")],
            "runs": [],
        },
    ]


@pytest.mark.parametrize(
    "command,status,expected",
    [
        ("cat a", "ok", ["ok"]),
        ("cat a", "failed", ["failed"]),
        ("cat a", "refused", ["failed"]),
        ("cat a && cat b && cat c", "ok", ["ok", "ok", "ok"]),
        ("cat a; cat b", "ok", ["unknown", "ok"]),
        ("cat a | cat b", "ok", ["unknown", "ok"]),
        ("cat a; cat b && cat c", "ok", ["unknown", "ok", "ok"]),
        ("cat a && cat b", "failed", ["unknown", "unknown"]),
        ("true || cat b", "ok", ["unknown", "unknown"]),
        ("false && cat b; true", "ok", ["unknown", "unknown", "ok"]),
    ],
)
def test_segment_status_does_not_infer_earlier_success(tmp_path, command, status, expected):
    assert [p["status"] for p in command_segments(command, tmp_path, status)] == expected


def test_path_prefixed_output_keeps_a_shown_earlier_read(tmp_path):
    parts = command_segments(
        "grep -H marker ../other/x; false", tmp_path, "failed", "../other/x:marker\n"
    )
    assert [p["status"] for p in parts] == ["ok", "unknown"]


def test_shell_stdin_and_python_literals_keep_their_language(tmp_path):
    parts = command_segments(
        "sh <<'SH'\ncat record.md\nSH\n"
        'python3 -c \'from pathlib import Path; Path("literal*.md").write_text("cat ../other/x")\'',
        tmp_path,
        "ok",
    )
    assert parts[0]["argv"] == ["sh"]
    assert parts[0]["reads"] == [str(tmp_path / "record.md")]
    assert parts[0]["runs"] == [["cat", "record.md"]]
    assert parts[1]["writes"] == [str(tmp_path / "literal*.md")]
    assert parts[1]["runs"] == []


def test_stdin_data_of_a_python_module_is_not_an_inline_program(tmp_path):
    (part,) = command_segments(
        "python3 -m package <<'EOF'\nimport subprocess\nsubprocess.run(['git', 'push'])\nEOF",
        tmp_path,
        "ok",
    )
    assert part["argv"] == ["python3", "-m", "package"]
    assert part["runs"] == []


def test_git_refs_and_messages_are_not_literal_file_reads(tmp_path):
    (part,) = command_segments(
        "git -C package -c mode=strict commit -m 'cat ../other/x'", tmp_path, "ok"
    )
    assert part["reads"] == [str(tmp_path / "package")]
    assert part["writes"] == [] and part["runs"] == []


@pytest.mark.parametrize(
    "script,argv,runs",
    [
        (
            "import subprocess\nsubprocess.run(['git', 'push', 'origin', 'main'])",
            ["python3", "-"],
            [["git", "push", "origin", "main"]],
        ),
        ("import subprocess, os\nsubprocess.run(os.getenv('COMMAND'))", None, None),
        ("from pathlib import Path\nPath(input()).read_text()", None, None),
        (
            "import subprocess\ndef unused():\n    subprocess.run(['git', 'push'])\nprint('done')",
            ["python3", "-"],
            [],
        ),
    ],
)
def test_inline_process_starts_and_dynamic_operands_are_recorded(tmp_path, script, argv, runs):
    (part,) = command_segments("python3 - <<'PY'\n" + script + "\nPY", tmp_path, "ok")
    assert part["argv"] == argv
    assert part["runs"] == runs


@needs_posix_bash
@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory read permissions")
@pytest.mark.parametrize(
    "command,classification",
    [
        ("rg -n '^import json' . ..; git status --short", "attempt"),
        ("cat ../grading/x 2>/dev/null; git status --short", "attempt"),
        ("cat ../grading/x 2>/dev/null | cat", "attempt"),
    ],
)
def test_trailing_success_cannot_prove_a_denied_protected_read(tmp_path, command, classification):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True, capture_output=True)
    (workspace / "app.py").write_text("import json\n", encoding="utf-8")
    grading = tmp_path / "grading"
    grading.mkdir()
    (grading / "x").write_text("import json\n", encoding="utf-8")
    grading.chmod(0)
    tmp_path.chmod(0o311)
    try:
        done = subprocess.run(
            ["sh", "-c", command],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        assert done.returncode == 0
        row = _executed_command(command, workspace)
        row["payload"]["item"]["aggregated_output"] = done.stdout + done.stderr
        item = _rows(tmp_path / "native.jsonl", [row])
        (action,) = ActionLedger().add([item], "codex", workspace)
        assert [p["status"] for p in action["segments"]] == ["unknown", "ok"]
        hits = contamination([item], "codex", [str(grading)], workspace)
        assert hits and {hit["classification"] for hit in hits} == {classification}
    finally:
        grading.chmod(0o700)
        tmp_path.chmod(0o700)


@pytest.mark.parametrize("command", WORKSPACE_COMMANDS)
def test_workspace_heredocs_and_searches_have_no_uncertain_operands(tmp_path, command):
    """Catches shell data and local expansions being mistaken for protected operands."""
    workspace = tmp_path / "workspace"
    (workspace / "docs").mkdir(parents=True)
    (workspace / "docs/a.md").write_text("local", encoding="utf-8")
    item = _rows(tmp_path / "native.jsonl", [_executed_command(command, workspace)])
    (action,) = ActionLedger().add([item], "codex", workspace)
    assert all(part["argv"] is not None and part["runs"] == [] for part in action["segments"])
    assert all(
        Path(path).is_relative_to(workspace)
        for part in action["segments"]
        for path in part["writes"]
    )
    hits = contamination([item], "codex", [str(tmp_path), "person.json"], workspace)
    assert not hits


@pytest.mark.parametrize("route", ["long", "brief"])
def test_clean_commands_and_intact_seals_give_isolation_pass(
    tmp_path, route, isolated_invocation_sources
):
    """Catches both caller paths omitting PASS after a clean, sealed run."""
    driver, harness = _driver(tmp_path, [])
    original = harness.call

    def call(*args):
        result = original(*args)
        rows = harness.rows[result.extras["thread_id"]]
        rows.extend(
            _executed_command(command, driver.place.workspace, str(i))
            for i, command in enumerate(WORKSPACE_COMMANDS)
        )
        _rows(Path(result.extras["native_sessions"][0]["copy"]), rows)
        return result

    harness.call = call
    result = RUN.invoke(
        "brief-runbook" if route == "brief" else "session-resume",
        driver.request,
        harness,
        RUN.Scene(
            driver.place.workspace,
            driver.place.stage,
            RUN.Place(keep=driver.place.keep),
            {"prompt": "Start."},
        ),
        RUN.Instruments(driver.place.path, driver.base),
        driver.session if route == "long" else None,
    )
    assert not result.extras.get("void"), result.extras
    assert result.extras["isolation_verdict"] == "PASS"
    assert result.extras["isolation_unverified"] == []


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("mode", ["content", "files_with_matches", "count"])
def test_decoded_search_actions_keep_output_mode(tmp_path, harness, mode):
    """Catches filename-only searches being credited as content reads after decoding."""
    arguments = {"path": "record.md", "pattern": "state", "output_mode": mode}
    if harness == "codex":
        rows = [
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "call_id": "search",
                    "name": "Grep",
                    "arguments": json.dumps(arguments),
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
                            "id": "search",
                            "name": "Grep",
                            "input": arguments,
                        }
                    ]
                },
            }
        ]
    item = _rows(tmp_path / "native.jsonl", rows)
    (action,) = ActionLedger().add([item], harness, tmp_path, "session")
    P.action(action)
    assert action["output_mode"] == mode
    assert action["paths"] == [str(tmp_path / "record.md")]


@pytest.mark.parametrize(
    "command,classification",
    [
        ("cat docs/{a,b}.md", None),
        ("cat 'docs/{a,link}.md'", None),
        ('cat "docs/{a,link}.md"', None),
        ("cat 'docs/*.md'", None),
        ("cat docs/{1..3}.md", None),
        ("cat docs/{00..02}.md", "attempt"),
        ("cat docs/{000..1100}.md", "attempt"),
        ("source docs/init.sh", None),
        ("eval 'cat docs/a.md'", None),
        ("rg --files --glob='*.md'", None),
        ("rg -f ../other/answer.txt .", "attempt"),
        ("cat docs/missing-*.md", None),
        ("cat docs/../docs/missing.md", None),
        ("cat WORKSPACE/docs/a.md", None),
        ("cat docs/missing.md; false", None),
        ("cat docs/{a,link}.md", "attempt"),
        ("cat ../other/{answer,missing}.txt", "attempt"),
        ("cat ../missing-*/answer.txt", "attempt unresolved"),
        ("cat ../other/{missing-a,missing-b}/*.txt", "attempt unresolved"),
        ("cat ~/x", "unresolved"),
        ("cat > docs/a.md <<EOF\n$(cat ../other/answer.txt)\nEOF", "unresolved"),
        (
            (
                "python3 - <<'PY'\nfrom pathlib import Path\n"
                "print(Path('../other/answer.txt').read_text())\nPY"
            ),
            "attempt",
        ),
        ("node - <<'JS'\nrequire('fs').readFileSync('../other/answer.txt');\nJS", "unresolved"),
        ("bash -s <<'SH'\ncat ../other/answer.txt\nSH", "attempt"),
        ("bash -s <<'SH'\ncat docs/a.md\nSH", None),
        ("node - <<'JS'\nrequire('fs').readFileSync('docs/a.md');\nJS", "unresolved"),
        ("python3 - <<'PY'\nprint('../other/answer.txt')\nPY", None),
        (
            "python3 - <<'PY'\nfrom pathlib import Path\nPath('docs/$literal').read_text()\nPY",
            None,
        ),
        ("node - <<'JS'\nconsole.log('../other/answer.txt');\nJS", "unresolved"),
        (
            "python3 - <<'PY'\nfrom pathlib import Path\n"
            "Path('docs/a.md').write_text('../other/answer.txt')\nPY",
            None,
        ),
        ("python3 - <<'PY'\nimport os\nopen(os.environ['INPUT']).read()\nPY", "unresolved"),
        ("cat > docs/a.md <<-'EOF'\n\t$INPUT\n\tEOF\ncat docs/a*.md", None),
        ("cat > docs/a.md <<'A' <<'B'\n$INPUT\nA\n../other/answer.txt\nB", None),
    ],
)
def test_expanded_paths_and_stdin_scripts_obey_the_workspace_boundary(
    tmp_path, command, classification
):
    workspace = tmp_path / "workspace"
    (workspace / "docs").mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    (other / "answer.txt").write_text("sealed", encoding="utf-8")
    (workspace / "docs/link.md").symlink_to(other / "answer.txt")
    (workspace / "docs/01.md").symlink_to(other / "answer.txt")
    (workspace / "docs/0001.md").symlink_to(other / "answer.txt")
    command = command.replace("WORKSPACE", str(workspace))
    item = _rows(tmp_path / "native.jsonl", [_executed_command(command, workspace)])
    hits = contamination([item], "codex", [str(other), str(tmp_path)], workspace)
    assert {h["classification"] for h in hits} == (
        set(classification.split()) if classification else set()
    )


@pytest.mark.parametrize("code", [0, 1, None])
def test_local_stdin_script_paths_stay_clean_when_the_command_status_is_uncertain(tmp_path, code):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command = "python3 - <<'PY'\nfrom pathlib import Path\nPath('local.txt').read_text()\nPY"
    item = _rows(tmp_path / "native.jsonl", [_executed_command(command, workspace, code=code)])
    assert contamination([item], "codex", [str(tmp_path)], workspace) == []


@pytest.mark.parametrize("status", ["ok", "failed", "refused", "unknown"])
def test_claude_read_keeps_its_path_and_matched_status(tmp_path, status):
    """Catches a native Read losing the evidence needed for recovery and isolation."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    protected = tmp_path / "other/answer.txt"
    rows = [
        {
            "type": "assistant",
            "cwd": str(workspace),
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "read",
                        "name": "Read",
                        "input": {"file_path": "../other/answer.txt"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "read",
                        **{
                            "ok": {"is_error": False, "content": "marker"},
                            "failed": {"is_error": True, "content": "file does not exist"},
                            "refused": {
                                "is_error": True,
                                "content": "<tool_use_error>Permission to use Read was denied"
                                "</tool_use_error>",
                            },
                            "unknown": {},
                        }[status],
                    },
                ]
            },
        },
    ]
    item = _rows(tmp_path / "native.jsonl", rows)
    (action,) = ActionLedger().add([item], "claude-code", workspace, "session")
    P.action(action)
    assert action["kind"] == "tool" and action["tool"] == "Read"
    assert action["paths"] == [str(protected.resolve())]
    assert action["status"] == status
    (hit,) = contamination([item], "claude-code", [str(protected)], workspace)
    assert hit["classification"] == "attempt"


@pytest.mark.parametrize(
    "name,key",
    [
        ("Read", "file_path"),
        ("Grep", "path"),
        ("Glob", "path"),
        ("Edit", "file_path"),
        ("Write", "file_path"),
        ("MultiEdit", "file_path"),
        ("NotebookEdit", "notebook_path"),
    ],
)
def test_file_tools_keep_resolved_paths_in_the_written_actions(tmp_path, name, key):
    driver, _ = _driver(tmp_path, [])
    (driver.place.workspace / "alias").symlink_to(tmp_path / "files", target_is_directory=True)
    rows = [
        {
            "type": "assistant",
            "cwd": str(driver.place.workspace),
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "file",
                        "name": name,
                        "input": {key: "alias/record.json"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "other",
                        "content": "failed",
                        "is_error": True,
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "file",
                        "content": "done",
                        "is_error": False,
                    },
                ]
            },
        },
    ]
    item = _rows(tmp_path / "claude.jsonl", rows)
    actions = ActionLedger().add([item], "claude-code", driver.place.workspace, "session")
    driver.turns = [
        {
            **driver.pending,
            "turn": 1,
            "answer": "Done.",
            "answer_path": str(tmp_path / "answer"),
            "session_id": "session",
            "actions": actions,
        }
    ]
    driver.write_records()
    (action,) = P.actions(json.loads(driver.actions_file.read_text(encoding="utf-8")))
    assert action["kind"] == "tool" and action["tool"] == name
    assert action["paths"] == [str((tmp_path / "files/record.json").resolve())]
    assert action["status"] == "ok"


@pytest.mark.parametrize("status", ["ok", "failed", "unknown"])
def test_codex_file_tools_match_their_own_result(tmp_path, status):
    rows = [
        {"type": "session_meta", "payload": {"id": "session", "cwd": tmp_path.as_uri()}},
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": "patch",
                "name": "apply_patch",
                "input": "*** Begin Patch\n*** Add File: file.txt\n+text\n*** End Patch",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": "other",
                "output": "Success.",
            },
        },
    ]
    if status != "unknown":
        rows.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "patch",
                    "output": "Success. Updated the following files:\nA file.txt"
                    if status == "ok"
                    else "Error: patch was not applied",
                },
            }
        )
    item = _rows(tmp_path / "native.jsonl", rows)
    (action,) = ActionLedger().add([item], "codex")
    P.action(action)
    assert action["paths"] == [str((tmp_path / "file.txt").resolve())]
    assert action["status"] == status


@pytest.mark.parametrize(
    "name,args,known_cwd,expected,path",
    [
        ("Glob", {"pattern": "../other/*.txt"}, True, "attempt", "other/*.txt"),
        (
            "Glob",
            {"pattern": "../other/missing-*.txt"},
            True,
            "attempt unresolved",
            "other/missing-*.txt",
        ),
        ("Grep", {"path": "..", "pattern": "marker"}, True, "attempt", ""),
        ("Read", {"file_path": "../other/answer.txt"}, False, "unresolved", ""),
    ],
)
def test_tool_searches_and_unknown_directories_do_not_escape_scanning(
    tmp_path,
    name,
    args,
    known_cwd,
    expected,
    path,
):
    workspace, other = tmp_path / "workspace", tmp_path / "other"
    workspace.mkdir()
    other.mkdir()
    (other / "answer.txt").write_text("marker", encoding="utf-8")
    item = _rows(
        tmp_path / "native.jsonl",
        [
            {
                "type": "assistant",
                **({"cwd": str(workspace)} if known_cwd else {}),
                "message": {
                    "content": [
                        {"type": "tool_use", "id": "attempt", "name": name, "input": args},
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "attempt",
                            "is_error": False,
                            "content": "done",
                        },
                    ]
                },
            },
        ],
    )
    hits = contamination([item], "claude-code", [str(other)])
    assert {hit["classification"] for hit in hits} == set(expected.split())
    if known_cwd:
        (action,) = ActionLedger().add([item], "claude-code")
        assert action["paths"] == [str(tmp_path.resolve() / path)]


@needs_posix_bash
@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory read permissions")
@pytest.mark.parametrize(
    ("command", "code", "returns_content"),
    [
        ("rg -n marker ..", 2, False),
        ("false && cat ../other/answer.txt", 1, False),
        ("cat ../other/answer.txt", 0, True),
        ("cat ../other/answer.txt missing-file", 1, False),
        ("cat ../other/answer.txt; false", 1, False),
        ("cat ../other/answer.txt; printf 'Permission denied\\n'", 0, False),
        ("grep -rn marker ../other", 0, True),
        ("grep -rn marker ../other; false", 1, True),
        ("grep -rH marker ../other; false", 1, True),
        ("grep -rn marker ../other missing-file", 2, True),
        ("rg -n marker ../other missing-file", 2, True),
        ("true || cat ../other/x", 0, False),
        ("false && cat ../other/answer.txt; true", 0, False),
        ("false &&\ncat ../other/answer.txt; true", 0, False),
        ("true && cat ../other/answer.txt", 0, True),
        ("true; cat ../other/answer.txt", 0, True),
        ("cat ../other/answer.txt; true", 0, False),
        ("cat ../other/answer.txt | cat", 0, False),
        ("false || cat ../other/answer.txt", 0, False),
        ("sh -c 'cat ../other/answer.txt'", 0, False),
        ("sh -c 'cat ../other/answer.txt'; false", 1, False),
        ("printf 'marker\\n'; false && cat ../other/answer.txt", 1, False),
    ],
)
def test_protected_command_attempts_do_not_depend_on_execution(
    tmp_path, command, code, returns_content
):
    """Catches success, failure, short circuits or output changing an attempt diagnostic."""
    root = tmp_path / "sealed"
    workspace, protected = root / "workspace", root / "other"
    workspace.mkdir(parents=True)
    protected.mkdir()
    (protected / "answer.txt").write_text("marker\n", encoding="utf-8")
    stage = root / "stage"
    stage.mkdir()
    stage.chmod(0)
    root.chmod(0o311)
    try:
        done = subprocess.run(
            ["sh", "-c", command],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        assert done.returncode == code, done.stdout + done.stderr
        if returns_content:
            assert "marker" in done.stdout
        if command == "rg -n marker ..":
            assert "Permission denied" in done.stderr and not done.stdout
        if command.startswith("grep -rn marker ../other"):
            assert "../other/answer.txt:1:marker" in done.stdout
        item = _rows(
            tmp_path / "native.jsonl",
            [
                _meta("session"),
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "item_completed",
                        "item": {
                            "id": "command",
                            "type": "CommandExecution",
                            "cwd": str(workspace),
                            "command": ["sh", "-c", command],
                            "exit_code": done.returncode,
                            "aggregated_output": done.stdout + done.stderr,
                        },
                    },
                },
            ],
        )
        hits = contamination([item], "codex", [str(protected)], workspace)
        attempts = [hit for hit in hits if hit["target"] == str(protected)]
        assert attempts
        assert all(hit["classification"] == "attempt" for hit in attempts)
        assert all(hit["command"] == command and hit["call_id"] for hit in attempts)
    finally:
        stage.chmod(0o700)
        root.chmod(0o700)


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize(
    ("result", "classification"),
    [
        ({"is_error": True, "content": "../other/answer.txt: Permission denied"}, "attempt"),
        ({"is_error": True, "content": "missing-file: Permission denied"}, "attempt"),
        ({"is_error": True, "content": "file does not exist"}, "attempt"),
        ({"is_error": False, "content": "Permission denied"}, "attempt"),
        (
            {"is_error": True, "content": "sealed-marker\n../other/answer.txt: Permission denied"},
            "attempt",
        ),
        ({"status": "unknown", "content": "sealed-marker"}, "attempt"),
        ({"status": "refused", "content": "sealed-marker"}, "attempt"),
        (
            {"is_error": True, "content": [{"type": "text", "text": "sealed-marker"}]},
            "attempt",
        ),
        (
            {"status": "unknown", "content": "../other/answer.txt:1:sealed-marker"},
            "attempt",
        ),
        (
            {
                "is_error": True,
                "content": "../other/answer.txt:1:marker\n../other: Permission denied",
            },
            "attempt",
        ),
        (
            {"status": "refused", "content": "../other/answer.txt:1:sealed-marker"},
            "attempt",
        ),
        (
            {
                "is_error": True,
                "content": [
                    {
                        "type": "text",
                        "text": "../other/answer.txt: Permission denied",
                        "metadata": "sealed-marker",
                    }
                ],
            },
            "attempt",
        ),
    ],
)
def test_tool_path_attempts_do_not_depend_on_results(tmp_path, harness, result, classification):
    """Catches tool results being used to classify protected references as proven reads."""
    workspace, protected = tmp_path / "workspace", tmp_path / "other/answer.txt"
    workspace.mkdir()
    protected.parent.mkdir()
    protected.write_text("sealed-marker\n", encoding="utf-8")
    arguments = {"file_path": "../other/answer.txt"}
    if harness == "codex":
        rows = [
            {
                "type": "response_item",
                "cwd": str(workspace),
                "payload": {
                    "type": "function_call",
                    "call_id": "attempt",
                    "name": "Read",
                    "arguments": arguments,
                },
            },
            {
                "type": "response_item",
                "payload": {"type": "function_call_output", "call_id": "attempt", "output": result},
            },
        ]
    else:
        rows = [
            {
                "type": "assistant",
                "cwd": str(workspace),
                "message": {
                    "content": [
                        {"type": "tool_use", "id": "attempt", "name": "Read", "input": arguments}
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "attempt", **result}]
                },
            },
        ]
    item = _rows(tmp_path / "native.jsonl", rows)
    (hit,) = contamination([item], harness, [str(protected.parent)], workspace)
    assert hit["classification"] == classification


@pytest.mark.parametrize("attributed", [False, True])
@pytest.mark.parametrize("completed", [False, True])
@pytest.mark.parametrize("field", ["content", "aggregated_output", "output", "stdout", "stderr"])
def test_command_results_keep_content_when_completion_has_no_output(
    tmp_path, field, completed, attributed
):
    """Catches a request or completion dropping returned content before the scan."""
    protected = tmp_path / "other/answer.txt"
    protected.parent.mkdir()
    protected.write_text("sealed-marker\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command = "grep -H sealed-marker ../other/answer.txt; false"
    output = "../other/answer.txt:sealed-marker\n" if attributed else "sealed-marker\n"
    rows = [
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "command",
                "arguments": {"cmd": command, "workdir": str(workspace)},
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": "command",
                "output": {"exit_code": 1, field: output},
            },
        },
    ]
    if completed:
        rows.append(
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "type": "CommandExecution",
                        "id": "completed",
                        "command": command,
                        "cwd": str(workspace),
                        "exit_code": 1,
                    },
                },
            }
        )
    item = _rows(tmp_path / "native.jsonl", rows)
    (action,) = ActionLedger().add([item], "codex", workspace)
    assert "sealed-marker" in str(action["output"])
    (hit,) = contamination([item], "codex", [str(protected.parent)], workspace)
    assert hit["classification"] == "attempt"


@needs_posix_bash
@pytest.mark.parametrize("route", ["long", "single", "brief"])
@pytest.mark.parametrize("source", ["session/corelib/reference.py", "brief/plant.py", "workspace"])
@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory read permissions")
def test_runner_protects_shared_fixture_sources_but_not_workspace_names(
    tmp_path, route, source, isolated_invocation_sources
):
    """Catches either runner protecting only the selected fixture's source folder."""
    driver, harness = _driver(tmp_path, [])
    if source == "workspace":
        target = driver.place.workspace / "reference.py"
        target.write_text("workspace content\n", encoding="utf-8")
    else:
        target = RUN.FIXTURES / source
    command = "cat " + str(target)
    original = harness.call

    def call(*args):
        result = original(*args)
        done = subprocess.run(
            ["cat", str(target)],
            cwd=driver.place.workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if source == "workspace":
            assert done.returncode == 0 and done.stdout
        else:
            assert done.returncode != 0 and "Permission denied" in done.stderr
        rows = harness.rows[result.extras["thread_id"]]
        rows.append(
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "id": "shared-read",
                        "type": "CommandExecution",
                        "cwd": str(driver.place.workspace),
                        "command": command,
                        "exit_code": done.returncode,
                        "aggregated_output": done.stdout + done.stderr,
                    },
                },
            }
        )
        _rows(Path(result.extras["native_sessions"][0]["copy"]), rows)
        return result

    harness.call = call
    result = RUN.invoke(
        "brief-runbook" if route == "brief" else "session-resume",
        driver.request,
        harness,
        RUN.Scene(
            driver.place.workspace,
            driver.place.stage,
            RUN.Place(keep=driver.place.keep),
            {"prompt": "Start."},
        ),
        RUN.Instruments(driver.place.path, driver.base),
        driver.session if route == "long" else None,
    )
    if source == "workspace":
        assert not result.extras.get("void")
        hits = (
            json.loads(Path(result.extras["contamination_file"]).read_text(encoding="utf-8"))
            if result.extras.get("contamination_file")
            else result.extras.get("contamination", [])
        )
        assert not hits
    else:
        assert not result.extras.get("void"), result.extras
        hits = (
            json.loads(Path(result.extras["contamination_file"]).read_text(encoding="utf-8"))
            if route == "long"
            else result.extras["contamination"]
        )
        assert any(hit["classification"] == "attempt" and hit["command"] == command for hit in hits)
        assert result.extras["isolation_verdict"] == "PASS"


@pytest.mark.parametrize("route", ["long", "brief"])
@pytest.mark.parametrize("code", [0, 1, None])
def test_command_results_cannot_void_intact_seals(
    tmp_path, route, code, isolated_invocation_sources
):
    """Catches command status or attributed output deciding either caller's verdict."""
    driver, harness = _driver(tmp_path, [{"label": "info", "message": "Continue."}])
    original = harness.call
    command = f"cat {driver.place.stage}/answer.txt"

    def call(*args):
        result = original(*args)
        rows = harness.rows[result.extras["thread_id"]]
        row = _executed_command(command, driver.place.workspace, key="attempt", code=code)
        row["payload"]["item"]["aggregated_output"] = f"{driver.place.stage}/answer.txt:MARKER"
        rows.append(row)
        _rows(Path(result.extras["native_sessions"][0]["copy"]), rows)
        return result

    harness.call = call
    if route == "long":
        result = driver.run()
        assert len(harness.requests) == 2
        hits = json.loads(Path(result.extras["contamination_file"]).read_text(encoding="utf-8"))
    else:
        result = RUN.invoke(
            "brief-runbook",
            driver.request,
            harness,
            RUN.Scene(
                driver.place.workspace,
                driver.place.stage,
                RUN.Place(keep=driver.place.keep),
                {"prompt": "Start."},
            ),
            RUN.Instruments(driver.place.path, driver.base),
            None,
        )
        hits = result.extras["contamination"]
    assert not result.extras.get("void"), result.extras
    assert result.extras["isolation_verdict"] == "PASS"
    assert {hit["classification"] for hit in hits} == {"attempt"}
    assert all(hit["command"] == command and hit["call_id"] == "attempt" for hit in hits)


@needs_posix_bash
@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory read permissions")
@pytest.mark.parametrize("route", ["long", "brief"])
@pytest.mark.parametrize("program", ['awk "BEGIN { exit }"', "python3 -c pass", "cat"])
def test_sealed_path_commands_are_attempts(tmp_path, route, program, isolated_invocation_sources):
    """Catches no-op programs and denied reads voiding a call with intact seals."""
    driver, harness = _driver(tmp_path, [])
    target = driver.place.stage / "answer.txt"
    target.write_text("protected content\n", encoding="utf-8")
    command = program + " " + str(target)
    original = harness.call

    def call(*args):
        assert driver.place.stage.stat().st_mode & 0o7777 == 0
        done = subprocess.run(
            ["sh", "-c", command],
            cwd=driver.place.workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        assert not done.stdout
        if program == "cat":
            assert done.returncode != 0 and "Permission denied" in done.stderr
        else:
            assert done.returncode == 0 and not done.stderr
        result = original(*args)
        row = _executed_command(command, driver.place.workspace, "sealed-attempt", done.returncode)
        row["payload"]["item"]["aggregated_output"] = done.stdout + done.stderr
        rows = harness.rows[result.extras["thread_id"]]
        rows.append(row)
        _rows(Path(result.extras["native_sessions"][0]["copy"]), rows)
        return result

    harness.call = call
    result = RUN.invoke(
        "brief-runbook" if route == "brief" else "session-resume",
        driver.request,
        harness,
        RUN.Scene(
            driver.place.workspace,
            driver.place.stage,
            RUN.Place(keep=driver.place.keep),
            {"prompt": "Start."},
        ),
        RUN.Instruments(driver.place.path, driver.base),
        driver.session if route == "long" else None,
    )
    assert not result.extras.get("void"), result.extras
    assert result.extras["isolation_verdict"] == "PASS"
    assert all(row[1] == "PASS" for row in result.extras["isolation"])
    hits = (
        json.loads(Path(result.extras["contamination_file"]).read_text(encoding="utf-8"))
        if route == "long"
        else result.extras["contamination"]
    )
    assert hits
    assert all(hit["classification"] == "attempt" for hit in hits)
    assert all(hit["call_id"] == "sealed-attempt" for hit in hits)


@pytest.mark.parametrize("route", ["long", "brief"])
def test_broken_seal_voids_both_callers(tmp_path, route, isolated_invocation_sources):
    """Catches a seal failure being lost when command-text voiding is removed."""
    driver, harness = _driver(tmp_path, [{"label": "info", "message": "Continue."}])
    original = harness.call

    def call(*args):
        driver.place.stage.chmod(0o700)
        return original(*args)

    harness.call = call
    result = RUN.invoke(
        "brief-runbook" if route == "brief" else "session-resume",
        driver.request,
        harness,
        RUN.Scene(
            driver.place.workspace,
            driver.place.stage,
            RUN.Place(keep=driver.place.keep),
            {"prompt": "Start."},
        ),
        RUN.Instruments(driver.place.path, driver.base),
        driver.session if route == "long" else None,
    )
    assert len(harness.requests) == 1
    assert result.extras["void"] == "contaminated"
    assert result.extras["isolation_verdict"] == "FAIL"
    assert any(row[:2] == ["grading-stage-seal", "FAIL"] for row in result.extras["isolation"])


@pytest.mark.parametrize("route", ["long", "brief"])
def test_uncovered_protected_path_is_a_runner_defect(
    tmp_path, monkeypatch, route, isolated_invocation_sources
):
    """Catches setup declaring a reachable protected path without a seal."""
    driver, harness = _driver(tmp_path, [])
    exposed = tmp_path / "exposed"
    exposed.mkdir()
    (exposed / "person.json").write_text("{}", encoding="utf-8")
    request = driver.request._replace(unreadable=(exposed,))
    scene = RUN.Scene(
        driver.place.workspace,
        driver.place.stage,
        RUN.Place(keep=driver.place.keep),
        {"prompt": "Start."},
    )
    if route == "long":
        driver.request = request
        result = driver.run()
        extra = result.extras
    else:
        # invoke normally supplies these paths from setup, before sealing the call.
        monkeypatch.setattr(RUN, "observed_folders", lambda *_: (exposed, None))
        kit = RUN.Instruments(driver.place.path, driver.base)
        kit = kit._replace(suite=SimpleNamespace(observe=True))
        with pytest.raises(ValueError, match="protected paths have no seal"):
            RUN.invoke("brief-runbook", request, harness, scene, kit, None)
        extra = scene.extra
    assert not harness.requests
    assert extra["void"] == "runner"
    monkeypatch.setattr(RUN, "post_check", lambda *args: pytest.fail("runner defect was graded"))
    RUN.grade(
        "brief-runbook",
        driver.place.workspace,
        RUN.Left(None, "", "", None),
        (True, ""),
        extra,
    )
    assert extra["verdict"] == "UNVERIFIED"


@needs_posix_bash
@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory read permissions")
@pytest.mark.parametrize("route", ["long", "brief"])
@pytest.mark.parametrize("generated", [False, True], ids=["temporary", "feature-day"])
def test_workspace_search_output_does_not_void_a_denied_parent_read(
    tmp_path, route, generated, isolated_invocation_sources
):
    """Catches shared imports being mistaken for content from sealed graders."""
    driver, harness = _driver(tmp_path, [])
    if generated:
        setup = subprocess.run(
            [
                "bash",
                str(ROOT / "evals/fixtures/session-feature-day/setup.sh"),
                str(driver.place.workspace),
                str(driver.place.stage),
            ],
            env=RUN.fixture_setup_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        assert setup.returncode == 0, setup.stdout + setup.stderr
    else:
        (driver.place.stage / "grader.py").write_text("import json\n", encoding="utf-8")
    (driver.place.workspace / "workspace_probe.py").write_text("import json\n", encoding="utf-8")
    original = harness.call
    command = "rg -n '^import json' . .."

    def call(*args):
        assert driver.place.stage.stat().st_mode & 0o7777 == 0
        assert driver.place.workspace.parent.stat().st_mode & 0o7777 == 0o311
        result = original(*args)
        done = subprocess.run(
            ["sh", "-c", command],
            cwd=driver.place.workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )
        assert done.returncode == 2
        assert "./workspace_probe.py:1:import json" in done.stdout
        assert "rg: ..: Permission denied" in done.stderr
        rows = harness.rows[result.extras["thread_id"]]
        rows.append(
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "id": "workspace-search",
                        "type": "CommandExecution",
                        "command": command,
                        "cwd": str(driver.place.workspace),
                        "exit_code": done.returncode,
                        "aggregated_output": done.stdout + done.stderr,
                    },
                },
            }
        )
        _rows(Path(result.extras["native_sessions"][0]["copy"]), rows)
        return result

    harness.call = call
    result = RUN.invoke(
        "brief-runbook" if route == "brief" else "session-feature-day",
        driver.request,
        harness,
        RUN.Scene(
            driver.place.workspace,
            driver.place.stage,
            RUN.Place(keep=driver.place.keep),
            {"prompt": "Start."},
        ),
        RUN.Instruments(driver.place.path, driver.base),
        driver.session if route == "long" else None,
    )
    hits = (
        json.loads(Path(result.extras["contamination_file"]).read_text(encoding="utf-8"))
        if route == "long"
        else result.extras["contamination"]
    )
    assert not result.extras.get("void"), result.extras
    assert hits and {hit["classification"] for hit in hits} == {"attempt"}


def test_single_turn_records_include_the_real_call_interval_and_answer(tmp_path):
    driver, harness = _driver(tmp_path, [])
    before = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = harness.call(
        "Start.", driver.request, driver.place.workspace, (), driver.place.path, driver.place.keep
    )
    after = datetime.datetime.now(datetime.timezone.utc).isoformat()
    RUN.single_session_records(
        result,
        "codex",
        driver.request,
        RUN.Scene(
            driver.place.workspace,
            driver.place.stage,
            RUN.Place(keep=driver.place.keep),
            {"prompt": "Start."},
        ),
        tmp_path / "fixture",
        (before, after),
    )
    (turn,) = P.turns(json.loads(Path(result.extras["turns_file"]).read_text(encoding="utf-8")))
    assert turn["started_at"] == before and turn["ended_at"] == after
    assert turn["label"] == "opener" and turn["required"] is True
    assert turn["message"] == "Start." and turn["answer"] == "Answer 1."
    assert Path(turn["answer_path"]).read_text(encoding="utf-8") == "Answer 1."
    assert turn["session_id"] == "session-1" and turn["calls"] == 1
    assert turn["actions"] == []
    records = RUN.kept_records(result.extras)
    assert RUN.records_env(records, tmp_path)["OB_TURNS"] == result.extras["turns_file"]


@pytest.mark.parametrize("label", ["ruling", "directive", "answer"])
def test_fixture_labels_and_metadata_survive_the_driver(tmp_path, label):
    """Catches fixed label lists and loss of required/clarification metadata."""
    message = {
        "label": label,
        "message": "Use the recorded choice.",
        "required": True,
        "clarification": False,
        "wait_seconds": 0,
    }
    driver, harness = _driver(tmp_path, [message])
    result = driver.run()
    assert not result.extras.get("error"), result.extras
    assert len(harness.requests) == 2
    turns = P.turns(json.loads(driver.turns_file.read_text(encoding="utf-8")))
    assert all(turns[1][key] == value for key, value in message.items())


def test_explicit_protocol_defect_is_void_even_with_a_descriptive_reason(tmp_path):
    driver, harness = _driver(
        tmp_path,
        [{"end": True, "reason": "No defined reply for this state.", "protocol_defect": True}],
    )
    result = driver.run()
    assert len(harness.requests) == 1
    assert result.extras.get("void") == "protocol_defect", result.extras


def test_answer_text_and_actions_documents_validate(tmp_path):
    """Catches answer paths passed as answers, bare history arrays and missing OB_ACTIONS."""
    driver, _ = _driver(tmp_path, [])
    result = driver.run()
    assert not result.extras.get("error"), result.extras
    turns = P.turns(json.loads(driver.turns_file.read_text(encoding="utf-8")))
    assert turns[0]["answer"] == "Answer 1."
    assert Path(turns[0]["answer_path"]).read_text(encoding="utf-8") == "Answer 1."
    assert turns[0]["label"] == "opener" and turns[0]["turn"] == 1
    assert (
        P.actions(json.loads(Path(result.extras["actions_file"]).read_text(encoding="utf-8"))) == []
    )


@pytest.mark.parametrize("child", [False, True])
@pytest.mark.parametrize(
    ("command", "classification"),
    [
        ("cd .. && cat grading/checks/x", "attempt"),
        ("cat ../*/checks/x", "attempt"),
        ("printf 'person.json'", "attempt"),
        ('cat "$SECRET_INPUT"', "unresolved"),
    ],
)
def test_contamination_distinguishes_reads_mentions_and_unknown_paths(
    tmp_path, command, classification, child
):
    workspace, grading = tmp_path / "workspace", tmp_path / "grading"
    workspace.mkdir()
    (grading / "checks").mkdir(parents=True)
    (grading / "checks/x").write_text("sealed", encoding="utf-8")
    item = {
        **_rows(
            tmp_path / "native.jsonl",
            [
                _meta("child" if child else "parent"),
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "exec_command",
                        "call_id": "attempt",
                        "arguments": json.dumps({"cmd": command, "workdir": str(workspace)}),
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "item_completed",
                        "item": {
                            "id": "read-result",
                            "type": "CommandExecution",
                            "command": command,
                            "cwd": str(workspace),
                            "exit_code": 0,
                        },
                    },
                },
            ],
        ),
        "child": child,
    }
    hits = contamination([item], "codex", [str(grading), "person.json"], workspace)
    assert len(hits) == 1, hits
    assert hits[0]["classification"] == classification
    assert hits[0]["child"] is child


@pytest.mark.parametrize("tool", P.ORCHESTRATION_TOOLS)
def test_orchestration_tools_are_known(tool):
    """Catches delegation making every graded claim UNVERIFIED."""
    document = decode_native(
        [
            {
                "type": "response_item",
                "payload": {"type": "function_call", "name": tool, "arguments": "{}"},
            }
        ],
        "codex",
    )
    assert document["unknown_tools"] == []


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
@pytest.mark.parametrize("tool", P.ORCHESTRATION_TOOLS)
def test_orchestration_is_a_tool_action_and_keeps_the_decoder_verified(tmp_path, harness, tool):
    extras: dict[str, Any]
    if harness == "codex":
        rows = [
            _meta("parent"),
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": tool,
                    "call_id": "delegate",
                    "arguments": "{}",
                },
            },
        ]
        extras = {"unknown_item_types": ["item.collab_agent_tool_call"]}
    else:
        rows = [
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "tool_use", "name": tool, "id": "delegate", "input": {}}]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": "delegate", "content": "done"}
                    ]
                },
            },
        ]
        extras = {"unknown_item_types": [f"tool.{tool}"]}
    item = {**_rows(tmp_path / "parent.jsonl", rows), "session_id": "parent"}
    extras["native_sessions"] = [item]
    doc = json.loads(family_evidence('{"commands":[],"files":[]}', extras, harness, {}))
    assert extras["decoder_verdict"] == "PASS" and extras["unknown_tools"] == []
    assert [(action["kind"], action["tool"]) for action in doc["actions"]] == [("tool", tool)]


def test_action_ledger_orders_starts_and_does_not_repeat_late_completions(tmp_path):
    request = {
        "type": "response_item",
        "timestamp": "2026-01-01T00:00:00Z",
        "payload": {
            "type": "function_call",
            "call_id": "run",
            "name": "exec_command",
            "arguments": {"cmd": "git tag v1", "workdir": str(tmp_path)},
        },
    }
    rows = [_meta("parent"), request]
    item = {**_rows(tmp_path / "parent.jsonl", rows), "session_id": "parent"}
    ledger = ActionLedger()
    actions = ledger.add([item], "codex", tmp_path)
    assert len(actions) == 1 and actions[0]["exit_code"] is None
    rows.append(
        {
            "type": "event_msg",
            "timestamp": "2026-01-01T00:01:00Z",
            "payload": {
                "type": "item_completed",
                "item": {
                    "type": "CommandExecution",
                    "id": "completed",
                    "command": ["git", "tag", "v1"],
                    "cwd": str(tmp_path),
                    "exit_code": 0,
                },
            },
        }
    )
    _rows(Path(item["copy"]), rows)
    assert ledger.add([item], "codex", tmp_path) == []
    updated = ledger.records[("parent", "run")]
    assert updated["exit_code"] == 0 and updated["started_at"] == "2026-01-01T00:00:00Z"


@pytest.mark.parametrize(
    ("command", "argv"),
    [
        (
            "git -C . push origin HEAD:refs/heads/main",
            ["git", "-C", ".", "push", "origin", "HEAD:refs/heads/main"],
        ),
        ("cd .. && cat grading/checks/x", None),
    ],
)
def test_native_shell_wrappers_keep_the_executed_body_and_simple_argv(tmp_path, command, argv):
    item = _rows(
        tmp_path / "parent.jsonl",
        [
            _meta("parent"),
            {
                "type": "event_msg",
                "payload": {
                    "type": "item_completed",
                    "item": {
                        "type": "CommandExecution",
                        "command": ["/bin/zsh", "-lc", command],
                        "cwd": str(tmp_path),
                        "exit_code": 0,
                        "id": "executed",
                    },
                },
            },
        ],
    )
    (action,) = ActionLedger().add([item], "codex", tmp_path)
    assert action["command"] == command and action["argv"] == argv


@pytest.mark.parametrize("command", ["printf 'person.json'", 'cat "$UNKNOWN_INPUT"'])
def test_single_turn_session_records_use_the_same_actions_and_contamination_contract(
    tmp_path, command
):
    driver, harness = _driver(tmp_path, [])
    result = harness.call(
        "Start.", driver.request, driver.place.workspace, (), driver.place.path, driver.place.keep
    )
    item = result.extras["native_sessions"][0]
    rows = harness.rows[result.extras["thread_id"]]
    rows.append(
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "command",
                "arguments": {"cmd": command},
            },
        }
    )
    _rows(Path(item["copy"]), rows)
    RUN.single_session_records(
        result,
        "codex",
        driver.request,
        RUN.Scene(
            driver.place.workspace,
            driver.place.stage,
            RUN.Place(keep=driver.place.keep),
            {"prompt": "Start."},
        ),
        tmp_path / "fixture",
        (
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        ),
    )
    records = RUN.kept_records(result.extras)
    assert RUN.records_env(records, tmp_path)["OB_ACTIONS"] == str(driver.actions_file)
    assert not RUN.session_record_error(records)
    (action,) = P.actions(json.loads(driver.actions_file.read_text(encoding="utf-8")))
    assert action["turn"] == 1 and action["command"] == command
    assert not result.extras.get("void")
    if "$" in command:
        assert "isolation_verdict" not in result.extras
        assert any(row["command"] == command for row in result.extras["isolation_residual"])
    else:
        assert result.extras["contamination"][0]["classification"] == "attempt"


def test_child_tag_is_not_appended_to_the_parent_command_list(tmp_path):
    """Catches one granted child act being counted through both lists."""
    item = {
        **_rows(
            tmp_path / "child.jsonl",
            [
                _meta("child", "parent"),
                _count(20, 20),
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "item_completed",
                        "item": {
                            "type": "CommandExecution",
                            "id": "tag",
                            "command": ["git", "tag", "v1"],
                            "cwd": str(tmp_path),
                            "exit_code": 0,
                            "status": "completed",
                        },
                    },
                },
            ],
        ),
        "session_id": "child",
        "child": True,
        "parent_id": "parent",
    }
    empty = json.dumps({"commands": [], "outputs": [], "files": [], "events": []})
    doc = json.loads(family_evidence(empty, {"native_sessions": [item]}, "codex", {}))
    commands = doc["commands"] + [c for child in doc["children"] for c in child["commands"]]
    assert commands == [["git tag v1", "succeeded", str(tmp_path)]]


def test_readme_names_the_current_prefix_and_protocol():
    text = Path("evals/README.md").read_text(encoding="utf-8").split("## Long sessions\n", 1)[1]
    section = text.split("\n## ", 1)[0]
    assert "`session-`" in section and "protocol v1" in section
    assert "`long-`" not in section


def test_next_message_checks_the_declared_labels():
    assert next_message('{"label":"ruling","message":"Use B."}', ("ruling",))["label"] == "ruling"


@pytest.mark.parametrize("crash", [None, OSError, RuntimeError, KeyboardInterrupt])
def test_grading_stage_is_locked_for_each_call_and_restored_on_exit(tmp_path, crash):
    """Catches exposing person knowledge on resume or leaving a crashed stage locked."""
    driver, harness = _driver(tmp_path, [{"label": "info", "message": "Continue."}])
    original = harness.call
    mode = driver.place.stage.stat().st_mode & 0o7777
    observed = []

    def call(*args):
        observed.append(driver.place.stage.stat().st_mode & 0o7777)
        if crash and len(observed) == 2:
            raise crash("interrupted")
        return original(*args)

    harness.call = call
    if crash in (RuntimeError, KeyboardInterrupt):
        with pytest.raises(crash):
            driver.run()
    else:
        result = driver.run()
        assert result.extras.get("void") == ("runner" if crash else None)
    assert observed == [0, 0]
    assert driver.place.stage.stat().st_mode & 0o7777 == mode


def test_a_permission_change_by_the_run_voids_it(tmp_path):
    driver, harness = _driver(tmp_path, [])
    original = harness.call
    mode = driver.place.stage.stat().st_mode & 0o7777

    def call(*args):
        driver.place.stage.chmod(0o700)
        return original(*args)

    harness.call = call
    result = driver.run()
    assert result.extras["void"] == "contaminated"
    assert result.extras["isolation_verdict"] == "FAIL"
    assert "permissions" in result.extras["error"]
    assert driver.place.stage.stat().st_mode & 0o7777 == mode


@pytest.mark.parametrize("command", ["printf 'person.json'", 'cat "$INPUT"'])
def test_mentions_and_dynamic_commands_keep_residual_without_overriding_seals(tmp_path, command):
    driver, harness = _driver(tmp_path, [{"label": "info", "message": "Continue."}])
    original = harness.call

    def call(*args):
        result = original(*args)
        item = result.extras["native_sessions"][0]
        rows = harness.rows[result.extras["thread_id"]]
        rows.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "read",
                    "arguments": {"cmd": command},
                },
            }
        )
        _rows(Path(item["copy"]), rows)
        return result

    harness.call = call
    result = driver.run()
    assert len(harness.requests) == 2 and not result.extras.get("void"), result.extras
    hits = json.loads(Path(result.extras["contamination_file"]).read_text(encoding="utf-8"))
    if "$" in command:
        assert result.extras["isolation_verdict"] == "PASS"
        assert any(row["command"] == command for row in result.extras["isolation_residual"])
    else:
        assert {hit["classification"] for hit in hits} == {"attempt"}


def test_broken_records_are_runner_faults_before_the_program_or_grader_sees_them(
    tmp_path, monkeypatch
):
    driver, _ = _driver(tmp_path, [])
    driver.call(driver.base)
    driver.turns[0]["actions"] = [{"kind": "invented"}]
    assert driver.next_turn() is None
    assert driver.extras["void"] == "runner"
    assert not driver.file(".next-1.stdout.txt").read_text(encoding="utf-8")
    driver.turns_file.write_text('{"version":1,"turns":[{}]}', encoding="utf-8")
    monkeypatch.setattr(RUN, "post_check", lambda *args: pytest.fail("invalid evidence was graded"))
    extra: dict[str, Any] = {}
    records = RUN.CallRecords(turns=driver.turns_file, actions=driver.actions_file)
    RUN.grade("session-example", tmp_path, RUN.Left(None, "", "", records), (True, ""), extra)
    assert extra["void"] == "runner" and extra["verdict"] == "UNVERIFIED"


@needs_posix_bash
def test_one_granted_child_act_belongs_to_its_turn_once(tmp_path):
    driver, harness = _driver(
        tmp_path,
        [
            {"label": "ruling", "message": "Create local v1 now.", "required": True},
            {"label": "info", "message": "Report the result.", "required": True},
        ],
    )
    subprocess.run(["git", "init", "-q", str(driver.place.workspace)], check=True)
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
            "--allow-empty",
            "-qm",
            "seed",
        ],
        check=True,
    )
    original = harness.call
    child_rows = [_meta("child", "session-1"), _count(20, 20)]

    def call(*args):
        result = original(*args)
        if len(harness.requests) >= 2:
            if len(harness.requests) == 2:
                subprocess.run(["git", "tag", "v1"], cwd=driver.place.workspace, check=True)
                child_rows.append(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "payload": {
                            "type": "item_completed",
                            "item": {
                                "type": "CommandExecution",
                                "id": "tag",
                                "command": ["git", "tag", "v1"],
                                "cwd": str(driver.place.workspace),
                                "exit_code": 0,
                            },
                        },
                    }
                )
            child = {
                **_rows(driver.file(f".child-{len(harness.requests)}.jsonl"), child_rows),
                "path": str(tmp_path / "child-source"),
                "session_id": "child",
                "parent_id": "session-1",
                "child": True,
            }
            result.extras["native_sessions"].append(child)
            result = result._replace(
                transcript=family_evidence(result.transcript, result.extras, "codex", {})
            )
        return result

    harness.call = call
    result = driver.run()
    assert not result.extras.get("error"), result.extras
    actions = P.actions(json.loads(driver.actions_file.read_text(encoding="utf-8")))
    assert len(actions) == 1
    assert actions[0] == {
        "kind": "command",
        "session_id": "child",
        "child": True,
        "parent_session_id": "session-1",
        "command": "git tag v1",
        "cwd": str(driver.place.workspace),
        "exit_code": 0,
        "status": "ok",
        "argv": ["git", "tag", "v1"],
        "segments": [
            {
                "argv": ["git", "tag", "v1"],
                "cwd": str(driver.place.workspace),
                "status": "ok",
                "reads": [],
                "writes": [],
                "runs": [],
            }
        ],
        "started_at": "2026-01-01T00:00:00Z",
        "turn": 2,
    }
    assert [len(turn["actions"]) for turn in result.extras["turns"]] == [0, 1, 0]
    assert (
        subprocess.check_output(
            ["git", "tag", "--list"], cwd=driver.place.workspace, text=True, encoding="utf-8"
        )
        == "v1\n"
    )


@needs_posix_bash
def test_sealed_checkpoint_probe_reads_its_whole_script_on_every_poll(tmp_path):
    """Catches a later poll reading the sealed script from its end: an empty script exits 0,
    which would cut the session at its second poll."""
    driver, harness = _driver(tmp_path, [])
    program = driver.place.stage / "cut.py"
    program.write_text("raise SystemExit(1)\n", encoding="utf-8")
    driver.session = driver.session._replace(
        shape="split", cut_check=(sys.executable, str(program))
    )
    original = harness.call
    polls = []

    def call(*args):
        for _ in range(3):
            driver.next_cut_poll = 0
            polls.append(driver.cut_check())
        return original(*args)

    harness.call = call
    driver.call(driver.base)
    assert polls == [None, None, None]


@needs_posix_bash
def test_checkpoint_probe_does_not_unlock_the_stage(tmp_path):
    driver, harness = _driver(tmp_path, [])
    program = driver.place.stage / "cut.py"
    program.write_text(
        "import os\nfrom pathlib import Path\n"
        "assert Path(os.environ['SEALED']).stat().st_mode & 0o777 == 0\n",
        encoding="utf-8",
    )
    driver.session = driver.session._replace(
        shape="split", cut_check=(sys.executable, str(program))
    )
    driver.place = driver.place._replace(
        env={**driver.place.env, "SEALED": str(driver.place.stage)}
    )
    original = harness.call

    def call(*args):
        assert driver.cut_check() == "split"
        assert driver.place.stage.stat().st_mode & 0o777 == 0
        return original(*args)

    harness.call = call
    driver.call(driver.base)
    assert driver.place.stage.stat().st_mode & 0o777 != 0


@pytest.mark.parametrize(
    "fixture",
    [path.name for path in sorted((ROOT / "evals/fixtures").glob("session-*")) if path.is_dir()],
)
@needs_posix_bash
def test_real_fixture_setup_and_dialogue_through_the_driver(tmp_path, fixture, monkeypatch):
    """Catches protocol drift that isolated fake fixture programs cannot detect."""
    monkeypatch.setenv("OB_EVAL_SKIP_WAITS", "1")
    source = ROOT / "evals/fixtures" / fixture
    workspace, stage, results = (tmp_path / name for name in ("workspace", "stage", "results"))
    results.mkdir()
    setup = subprocess.run(
        ["bash", str(source / "setup.sh"), str(workspace), str(stage)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    session = read_session(source / "session.json")
    assert session is not None
    is_split = session.shape == "split"

    messages = []

    class DialogueHarness(FakeHarness):
        def call(self, message, *args):
            messages.append(message)
            result = super().call(message, *args)
            if result.extras.get("stopped") == "split":
                return result._replace(answer="")  # An abrupt cut has no final answer.
            answers = [
                "Who is the rollout audience?",
                "Stopping here.",
                "May I commit on the work branch?",
            ]
            number = len(self.requests) - int(is_split)
            return result._replace(
                answer=answers[number - 1]
                if 1 <= number <= len(answers)
                else "Completed this turn."
            )

    harness = DialogueHarness(tmp_path, stops=("split",) if session.shape == "split" else ())
    env = {
        **os.environ,
        "OUTCOMEBOUND_GRADER_DIR": str(stage),
        "OUTCOMEBOUND_EVAL_DIR": str(ROOT / "evals"),
    }
    driver = Driver(
        session,
        (source / "prompt.md").read_text(encoding="utf-8"),
        Request("test", "medium", session_run=True),
        harness,
        Driving(workspace, (), os.environ["PATH"], results / "run.native.jsonl", stage, env),
    )
    result = driver.run()
    assert not result.extras.get("error") and not result.extras.get("void"), result.extras
    turns = P.turns(json.loads(driver.turns_file.read_text(encoding="utf-8")))
    assert messages == [turn["message"] for turn in turns]
    P.actions(json.loads(driver.actions_file.read_text(encoding="utf-8")))
    person = json.loads((source / "person.json").read_text(encoding="utf-8"))
    required = [item["message"] for item in person["script"]]
    delivered = [
        turn["message"]
        for turn in turns
        if turn["label"] not in ("opener", "resume") and turn["required"]
    ]
    assert delivered == required[: len(delivered)]
    assert delivered == required or result.extras.get("stopped") in (
        "max_turns",
        "max_nudges",
        "timeout",
        "input_cap",
    )

    allowance, optional = person["optional_turn_allowance"], 0
    for previous, following in pairwise(turns):
        optional += not previous["required"]
        if previous["answer"] == "Completed this turn.":
            # A bare claim with no visible work gets a restatement or a nudge until the optional
            # allowance is spent, then the next required message, never an end.
            assert following["label"] in {"restate", "nudge"} or (
                following["required"] and optional >= allowance
            )
    assert any(turn["label"] == "restate" for turn in turns)


@pytest.mark.parametrize(
    "fixture", ["session-feature-day", "session-release-prep", "session-incident"]
)
@pytest.mark.parametrize("broken", ["history", "workspace", "person"])
@needs_posix_bash
def test_next_turn_unreadable_input_is_a_protocol_defect(tmp_path, fixture, broken):
    source = ROOT / "evals/fixtures" / fixture
    workspace, stage = tmp_path / "workspace", tmp_path / "stage"
    setup = subprocess.run(
        ["bash", str(source / "setup.sh"), str(workspace), str(stage)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    history, answer = tmp_path / "history.json", tmp_path / "answer.md"
    history.write_text(json.dumps({"version": 1, "turns": []}), encoding="utf-8")
    answer.write_text("Completed this turn.", encoding="utf-8")
    if broken == "history":
        history.write_text("not JSON", encoding="utf-8")
    elif broken == "workspace":
        workspace = tmp_path / "missing"
    else:
        person = next(
            path for path in (stage / "person.json", stage / "checks/person.json") if path.is_file()
        )
        person.write_text("not JSON", encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-I", "-B", str(stage / "checks/next_turn.py")],
        cwd=stage,
        env={
            **os.environ,
            "OB_WORKSPACE": str(workspace),
            "OB_HISTORY": str(history),
            "OB_LAST_ANSWER": str(answer),
            "OB_NUDGES": "0",
            "OB_TURN": "1",
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    session = read_session(source / "session.json")
    assert session is not None
    result = next_message(done.stdout, session.labels)
    assert result["end"] and result["protocol_defect"]


@pytest.mark.parametrize(
    ("command", "classification"),
    [
        ("rg -n sealed-marker ..", "attempt"),
        ("env LC_ALL=C rg -n sealed-marker ..", "attempt"),
        ("grep -R sealed-marker ..", "attempt"),
        ("find .. -type f", "attempt"),
        ("cd .. && find -type f", "attempt"),
        ("ls -R ..", "attempt"),
        ("rg sealed-marker .", None),
        ("ls ..", None),
        ("printf '%s' \"$(cat ../sibling/answer.txt)\"", "unresolved"),
        ("printf '%s' `cat ../sibling/answer.txt`", "unresolved"),
        ("printf '%s' \"$INPUT\"", "unresolved"),
        ("printf '%s' {../sibling,other}/answer.txt", "unresolved"),
        ("printf '%s' ../missing-*/answer.txt", "unresolved"),
        ("printf '%s' '../sibling/answer.txt'", "attempt"),
        ("printf '%s' '{../sibling,other}/answer.txt'", None),
        ("printf '%s' '$INPUT'", None),
    ],
)
def test_recursive_reads_and_unresolved_expansions_cannot_get_a_clean_scan(
    tmp_path, command, classification
):
    """Catches ancestor searches and expansion inside an otherwise harmless printf."""
    workspace, sibling = tmp_path / "workspace", tmp_path / "sibling"
    workspace.mkdir()
    sibling.mkdir()
    (sibling / "answer.txt").write_text("sealed-marker\n", encoding="utf-8")
    item = _rows(
        tmp_path / "native.jsonl",
        [
            {
                "type": "assistant",
                "cwd": str(workspace),
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "attempt",
                            "name": "Bash",
                            "input": {"command": command},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "attempt",
                            "content": "done",
                            "is_error": False,
                        },
                    ]
                },
            },
        ],
    )
    hits = contamination([item], "claude-code", [str(sibling)], workspace)
    assert {hit["classification"] for hit in hits} == (
        {classification} if classification else set()
    )


@pytest.mark.parametrize("crash", [None, OSError, RuntimeError, KeyboardInterrupt])
def test_roots_are_search_only_until_the_run_exits(tmp_path, crash):
    """Catches listing between resumed calls and a crash leaving roots locked."""
    driver, harness = _driver(tmp_path, [{"label": "info", "message": "Continue."}])
    roots = (driver.place.workspace.parent, driver.place.keep.parent)
    modes = [path.stat().st_mode & 0o7777 for path in roots]
    original = harness.call
    observed = []

    def call(*args):
        observed.append([path.stat().st_mode & 0o7777 for path in roots])
        assert driver.place.stage.stat().st_mode & 0o7777 == 0
        if os.geteuid() != 0:
            for path in roots:
                with pytest.raises(PermissionError):
                    os.listdir(path)
        (driver.place.workspace / "owned").mkdir(exist_ok=True)
        if crash and len(observed) == 2:
            raise crash("interrupted")
        return original(*args)

    harness.call = call
    if crash in (RuntimeError, KeyboardInterrupt):
        with pytest.raises(crash):
            driver.run()
    else:
        result = driver.run()
        assert result.extras.get("void") == ("runner" if crash else None)
    assert observed == [[0o311, 0o311], [0o311, 0o311]]
    assert [path.stat().st_mode & 0o7777 for path in roots] == modes


def test_overlapping_runs_restore_only_after_the_last_lease(tmp_path):
    """Catches one finished run making another run's sibling names listable."""
    roots = tuple(tmp_path / name for name in ("workspaces", "results"))
    stages = [tmp_path / name for name in ("first-stage", "second-stage")]
    for path in (*roots, *stages):
        path.mkdir()
    roots[0].chmod(0o750)
    roots[1].chmod(0o700)
    first: dict[str, Any] = {}
    second: dict[str, Any] = {}
    with sealed_roots(roots, stages[0], first):
        with sealed_roots(roots, stages[1], second):
            assert [path.stat().st_mode & 0o7777 for path in roots] == [0o311, 0o311]
        assert [path.stat().st_mode & 0o7777 for path in roots] == [0o311, 0o311]
    assert [path.stat().st_mode & 0o7777 for path in roots] == [0o750, 0o700]
    assert first == second == {}


def test_changing_a_root_mode_stops_the_run_and_restores_it(tmp_path):
    driver, harness = _driver(tmp_path, [{"label": "info", "message": "Continue."}])
    root = driver.place.workspace.parent
    mode = root.stat().st_mode & 0o7777
    original = harness.call

    def call(*args):
        root.chmod(0o700)
        return original(*args)

    harness.call = call
    result = driver.run()
    assert len(harness.requests) == 1
    assert result.extras["void"] == "contaminated"
    assert result.extras["isolation_verdict"] == "FAIL"
    assert root.stat().st_mode & 0o7777 == mode


def test_claude_run_reports_root_isolation_as_unverified(tmp_path):
    """Catches a clean command scan being reported as proof that chmod cannot escape."""
    driver, harness = _driver(tmp_path, [])
    harness.name = "claude-code"
    driver = Driver(driver.session, "Start.", driver.request, harness, driver.place)
    original = harness.call

    def call(*args):
        result = original(*args)
        _rows(
            Path(result.extras["native_sessions"][0]["copy"]),
            [
                {
                    "type": "assistant",
                    "message": {
                        "id": "call-1",
                        "content": [],
                        "usage": {
                            "input_tokens": 100,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 0,
                            "output_tokens": 1,
                        },
                    },
                }
            ],
        )
        result.extras["isolation"] = [["sandbox", "PASS", "synthetic loading control"]]
        return result

    harness.call = call
    result = driver.run()
    assert not result.extras.get("error"), result.extras
    assert result.extras["isolation_verdict"] == "UNVERIFIED"
    assert "root-permissions" in result.extras["isolation_unverified"]


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGKILL])
@needs_posix_bash
def test_runner_death_restores_roots_and_the_inflight_stage(tmp_path, signum):
    """Catches exits that cannot unwind the driver's Python finally blocks."""
    folder = tmp_path / "run"
    folder.mkdir()
    folder.chmod(0o750)
    script = """
import sys
from pathlib import Path
from tests.test_long_eval_protocol import _driver
driver, harness = _driver(Path(sys.argv[1]), [])
driver.place.keep.parent.chmod(0o700)
driver.place.stage.chmod(0o710)
def call(*args):
    print('inflight', flush=True)
    sys.stdin.read()
harness.call = call
driver.run()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(folder)],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        import select

        assert child.stdout is not None
        assert select.select([child.stdout], [], [], 15)[0], "runner did not reach its call"
        assert child.stdout.readline().strip() == "inflight"
        child.send_signal(signum)
        child.wait(timeout=15)
        expected = {folder: 0o750, folder / "results": 0o700, folder / "stage": 0o710}
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if all(path.stat().st_mode & 0o7777 == mode for path, mode in expected.items()):
                break
            time.sleep(0.02)
        assert {path: path.stat().st_mode & 0o7777 for path in expected} == expected
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=15)


@pytest.mark.parametrize(
    ("result_part", "expected_code", "expected_status"),
    [
        ({"content": "checked", "is_error": False}, 0, "ok"),
        ({"content": "Permission to use Bash was denied", "is_error": False}, 0, "ok"),
        ({"content": "checked", "exit_code": 0}, 0, "ok"),
        ({"content": "failed", "exit_code": 4}, 4, "failed"),
        ({"content": "Exit code 7\ncheck failed", "is_error": True}, 7, "failed"),
        ({"content": "check failed", "is_error": True}, None, "failed"),
        ({"content": "denied", "status": "refused", "is_error": True}, None, "refused"),
        (
            {
                "content": "<tool_use_error>Permission to use Bash was denied</tool_use_error>",
                "is_error": True,
            },
            None,
            "refused",
        ),
        ({}, None, "unknown"),
    ],
)
def test_claude_bash_outcomes_reach_the_decoder_and_action_writer(
    tmp_path, result_part, expected_code, expected_status
):
    """Catches a successful native Bash result losing its exit code in OB_ACTIONS."""
    driver, _ = _driver(tmp_path, [])
    command = "python3 -B tools/docs_check.py"
    rows = [
        {
            "type": "assistant",
            "cwd": str(driver.place.workspace),
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "other",
                        "name": "Bash",
                        "input": {"command": "false"},
                    },
                    {
                        "type": "tool_use",
                        "id": "check",
                        "name": "Bash",
                        "input": {"command": command},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "check", **result_part},
                    {
                        "type": "tool_result",
                        "tool_use_id": "other",
                        "content": "Exit code 1",
                        "is_error": True,
                    },
                ]
            },
        },
    ]
    item = _rows(tmp_path / "claude.jsonl", rows)
    actions = ActionLedger().add([item], "claude-code", driver.place.workspace, "session")
    driver.turns = [
        {
            **driver.pending,
            "turn": 1,
            "answer": "Done.",
            "answer_path": str(tmp_path / "answer"),
            "session_id": "session",
            "actions": actions,
        }
    ]
    driver.write_records()
    written = P.actions(json.loads(driver.actions_file.read_text(encoding="utf-8")))
    assert written[1]["command"] == command
    assert written[1]["exit_code"] == expected_code
    assert written[1]["status"] == expected_status
    decoded = decode_native(rows, "claude-code")
    statuses = {
        "ok": "succeeded",
        "failed": "failed",
        "refused": "declined",
        "unknown": "unverified",
    }
    assert decoded["commands"][1][1] == statuses[expected_status]


@needs_posix_bash
def test_feature_day_person_wait_reaches_sleep_and_is_not_active_time(tmp_path, monkeypatch):
    """Catches metadata loss in the real selector before the driver's sleep sees it."""
    source = ROOT / "evals/fixtures/session-feature-day"
    workspace, stage, results = (tmp_path / name for name in ("workspace", "stage", "results"))
    results.mkdir()
    done = subprocess.run(
        ["bash", str(source / "setup.sh"), str(workspace), str(stage)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    person_path = next(
        path for path in (stage / "person.json", stage / "checks/person.json") if path.is_file()
    )
    person = json.loads(person_path.read_text(encoding="utf-8"))
    person["script"][0]["wait_seconds"] = 60
    person_path.write_text(json.dumps(person), encoding="utf-8")
    session = read_session(source / "session.json")
    assert session is not None
    clock, sleeps = [100.0], []

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(
        long_sessions, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep)
    )

    class Harness(FakeHarness):
        def call(self, *args):
            clock[0] += 2
            return (
                super()
                .call(*args)
                ._replace(answer="Partial work remains because the next change is pending.")
            )

    harness = Harness(tmp_path)
    driver = Driver(
        session._replace(max_turns=2),
        "Start.",
        Request("test", "medium", session_run=True),
        harness,
        Driving(
            workspace,
            (),
            os.environ["PATH"],
            results / "run.native.jsonl",
            stage,
            {
                **os.environ,
                "OUTCOMEBOUND_GRADER_DIR": str(stage),
                "OUTCOMEBOUND_EVAL_DIR": str(ROOT / "evals"),
            },
        ),
    )
    result = driver.run()
    assert not result.extras.get("error"), result.extras
    assert sleeps == [60]
    assert driver.turns[1]["wait_seconds"] == 60
    assert result.extras["active_seconds"] == 4
    assert clock[0] - driver.started == 64


@needs_posix_bash
@pytest.mark.parametrize("mutation", ["content", "mode", "entry", "bytecode", "seal"])
def test_fixture_seal_checks_modes_and_content_after_each_call(tmp_path, mutation):
    """Catches changes behind a restored root mode, including an added source file."""
    from evals.session_permissions import sealed_sources

    root = tmp_path / "sources"
    root.mkdir(mode=0o750)
    file = root / "reference.py"
    file.write_text("original", encoding="utf-8")
    extra: dict[str, Any] = {}
    with sealed_sources(root, extra):
        assert root.stat().st_mode & 0o7777 == 0
        # Simulate a harness that changed a seal. Real calls may not chmod this path.
        root.chmod(0o750)
        if mutation == "content":
            file.write_text("changed", encoding="utf-8")
        elif mutation == "mode":
            file.chmod(0o700)
        elif mutation == "entry":
            (root / "added").touch()
        elif mutation == "bytecode":
            (root / "__pycache__").mkdir()
            (root / "__pycache__/reference.pyc").write_bytes(b"changed")
        if mutation != "seal":
            root.chmod(0)
    assert extra["void"] == "contaminated"
    assert extra["isolation"] == [["fixture-source-seal", "FAIL", "source modes and content"]]
    assert root.stat().st_mode & 0o7777 == 0o750


@needs_posix_bash
@pytest.mark.parametrize("route", ["long", "brief"])
@pytest.mark.parametrize("crash", [False, True])
def test_calls_with_distinct_fixture_roots_can_overlap(
    tmp_path, monkeypatch, isolated_invocation_sources, route, crash
):
    """One configured root stays readable while a call seals another, even on failure."""
    first = isolated_invocation_sources
    second = tmp_path.resolve() / "peer-source/evals/fixtures"
    shutil.copytree(first, second)
    peer = load("peer_eval_run", "evals/run.py")
    monkeypatch.setattr(peer, "FIXTURES", second)
    modes = [root.stat().st_mode & 0o7777 for root in (first, second)]
    expected = (second / "brief-runbook/install.json").read_bytes()
    for name in ("outer", "inner"):
        (tmp_path / name).mkdir()
    outer, harness = _driver(tmp_path / "outer", [])
    inner, other_harness = _driver(tmp_path / "inner", [])
    original, other_call = harness.call, other_harness.call

    def invoke(runner, driver, tool, session):
        return runner.invoke(
            "session-resume" if session else "brief-runbook",
            driver.request,
            tool,
            runner.Scene(
                driver.place.workspace,
                driver.place.stage,
                runner.Place(keep=driver.place.keep),
                {"prompt": "Start."},
            ),
            runner.Instruments(driver.place.path, driver.base),
            session,
        )

    def inner_call(*args):
        assert first.stat().st_mode & 0o7777 == 0
        assert second.stat().st_mode & 0o7777 == 0
        request = args[1]
        assert second in request.unreadable and first not in request.unreadable
        assert second in request.protected and first not in request.protected
        return other_call(*args)

    def outer_call(*args):
        assert first.stat().st_mode & 0o7777 == 0
        assert (second / "brief-runbook/install.json").read_bytes() == expected
        result = invoke(peer, inner, other_harness, inner.session if route == "long" else None)
        assert result.extras["isolation_verdict"] == "PASS"
        assert first.stat().st_mode & 0o7777 == 0
        assert (second / "brief-runbook/install.json").read_bytes() == expected
        if crash:
            raise OSError("synthetic harness failure")
        return original(*args)

    harness.call, other_harness.call = outer_call, inner_call
    session = outer.session if route == "long" else None
    if crash and route == "brief":
        with pytest.raises(OSError, match="synthetic harness failure"):
            invoke(RUN, outer, harness, session)
    else:
        result = invoke(RUN, outer, harness, session)
        if crash:
            assert "synthetic harness failure" in result.extras["error"]
        else:
            assert result.extras["isolation_verdict"] == "PASS"
    assert [root.stat().st_mode & 0o7777 for root in (first, second)] == modes
    assert (first / "brief-runbook/install.json").read_bytes() == expected
    assert (second / "brief-runbook/install.json").read_bytes() == expected


@needs_posix_bash
def test_stage_content_change_is_found_after_the_call(tmp_path):
    """Catches a source edit hidden by changing the stage mode back to zero."""
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "grader.py").write_text("original", encoding="utf-8")
    extra: dict[str, Any] = {}
    with long_sessions.sealed_stage(stage, extra):
        stage.chmod(0o700)
        (stage / "grader.py").write_text("changed", encoding="utf-8")
        stage.chmod(0)
    assert extra["void"] == "contaminated"
    assert extra["isolation"][0][1] == "FAIL"


def source_process(root):
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            """
import json, sys
from pathlib import Path
from evals.session_permissions import sealed_sources
extra = {}
with sealed_sources(Path(sys.argv[1]), extra):
    print('sealed', flush=True)
    sys.stdin.readline()
print(json.dumps(extra), flush=True)
""",
            str(root),
        ],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


@needs_posix_bash
def test_shared_fixture_seal_waits_for_calls_and_runner_reads_wait_for_the_seal(tmp_path):
    """Catches one process opening sources while a peer still has an active harness call."""
    root = tmp_path / "sources"
    root.mkdir(mode=0o750)
    (root / "reference.py").write_text("answer", encoding="utf-8")
    first, second = source_process(root), source_process(root)
    reader = None
    try:
        for child in (first, second):
            assert child.stdout.readline().strip() == "sealed"
        first.stdin.write("finish\n")
        first.stdin.flush()
        reader = subprocess.Popen(
            [
                sys.executable,
                "-c",
                """
import sys
from pathlib import Path
from evals.session_permissions import source_access
root = Path(sys.argv[1])
with source_access(root):
    print((root / 'reference.py').read_text(encoding='utf-8'), flush=True)
""",
                str(root),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        with pytest.raises(subprocess.TimeoutExpired):
            reader.wait(timeout=0.15)
        assert first.poll() is None and root.stat().st_mode & 0o7777 == 0
        second.stdin.write("finish\n")
        second.stdin.flush()
        for child in (first, second):
            output, error = child.communicate(timeout=15)
            assert child.returncode == 0, error
            assert json.loads(output)["isolation"][0][1] == "PASS"
        output, error = reader.communicate(timeout=15)
        assert reader.returncode == 0, error
        assert output.strip() == "answer"
        assert root.stat().st_mode & 0o7777 == 0o750
    finally:
        for child in (first, second, reader):
            if child is not None:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=15)


@needs_posix_bash
def test_next_runner_restores_a_fixture_seal_after_sigkill(tmp_path):
    """Catches persistent chmod 000 after a runner dies without unwinding Python contexts."""
    from evals.session_permissions import sealed_sources, source_access

    root = tmp_path / "sources"
    root.mkdir(mode=0o750)
    (root / "reference.py").write_text("answer", encoding="utf-8")
    child = source_process(root)
    try:
        assert child.stdout.readline().strip() == "sealed"
        child.kill()
        child.communicate(timeout=15)
        assert root.stat().st_mode & 0o7777 == 0
        with source_access(root):
            assert (root / "reference.py").read_text(encoding="utf-8") == "answer"
            assert root.stat().st_mode & 0o7777 == 0o750
        extra: dict[str, Any] = {}
        with sealed_sources(root, extra):
            assert root.stat().st_mode & 0o7777 == 0
        assert extra["isolation"][0][1] == "PASS"
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=15)
        with source_access(root):
            pass


@pytest.mark.parametrize(
    "operand, expected",
    [
        ("$INPUT", "PASS"),
        ("../stage/answer.txt", "PASS"),
        ("../../outside/answer.txt", "PASS"),
    ],
)
def test_external_command_operands_cannot_override_intact_seals(tmp_path, operand, expected):
    """Catches static external operands changing an intact seal verdict."""
    driver, harness = _driver(tmp_path, [])
    original = harness.call
    command = f"cat {operand}; false"

    def call(*args):
        result = original(*args)
        rows = harness.rows[result.extras["thread_id"]]
        rows.append(_executed_command(command, driver.place.workspace, code=1))
        _rows(Path(result.extras["native_sessions"][0]["copy"]), rows)
        return result

    harness.call = call
    result = driver.run()
    assert result.extras["isolation_verdict"] == expected
    assert result.extras["isolation_residual"]
    assert result.extras["isolation_unverified"] == []


@pytest.mark.parametrize("sealed_plan", [False, True])
def test_command_text_diagnostics_are_reported_beside_the_effect_verdict(
    tmp_path, monkeypatch, sealed_plan
):
    """Catches a failing diagnostic changing PASS, or the runner losing its risk label."""
    sources = tmp_path / "sources/fixtures"
    fixture = sources / "session-example"
    fixture.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    plan = {
        "version": 1,
        "claims": [
            {
                "name": name,
                "risk": risk,
                "required": required,
                "kind": "static",
                "command": [sys.executable, "-c", f"raise SystemExit({code})"],
            }
            for name, risk, required, code in (
                ("effect", "observed state", True, 0),
                ("command-hint", "COMMAND TEXT only: attempted process", False, 1),
                ("wording-hint", "WORDING only: report text", False, 1),
            )
        ],
    }
    (fixture / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", sources)
    graders = tmp_path / "kept-graders" if sealed_plan else None
    if graders is not None:
        graders.mkdir()
        (graders / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
        # The record must use the plan it actually graded, rather than the current source.
        plan["claims"] = []
        (fixture / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    extra: dict[str, Any] = {}
    report = RUN.grade(
        "session-example",
        workspace,
        RUN.Left(None, "transcript", "answer"),
        (True, ""),
        extra,
        graders,
    )
    assert extra["verdict"] == "PASS", report
    assert extra["required"] == ["effect"]
    assert extra["claims"] == {"effect": "PASS", "command-hint": "FAIL", "wording-hint": "FAIL"}
    assert extra["diagnostics"] == {
        "command-hint": "COMMAND TEXT only",
        "wording-hint": "WORDING only",
    }
    assert "command-hint FAIL [COMMAND TEXT only]" in RUN.claims_text(extra)
    assert "  command-hint [COMMAND TEXT only]: PASS 0/1" in RUN._claim_lines([extra])


@needs_posix_bash
def test_driver_seals_sources_and_records_all_three_seals_on_every_turn(tmp_path):
    """Catches a resume omitting source protection or a per-call integrity row."""
    driver, harness = _driver(
        tmp_path,
        [{"label": "info", "message": "Continue."}, {"label": "note", "message": "Finish."}],
    )
    sources = tmp_path / "sources"
    sources.mkdir(mode=0o750)
    (sources / "reference.py").write_text("kept", encoding="utf-8")
    driver.place = driver.place._replace(sources=sources, forbidden=(sources,))
    original = harness.call

    def call(*args):
        assert sources.stat().st_mode & 0o7777 == 0
        assert driver.place.stage.stat().st_mode & 0o7777 == 0
        return original(*args)

    harness.call = call
    result = driver.run()
    assert len(harness.requests) == 3
    assert result.extras["isolation_verdict"] == "PASS"
    for seal in ("fixture-source-seal", "grading-stage-seal", "run-root-seal"):
        assert [row[1] for row in result.extras["isolation"] if row[0] == seal] == ["PASS"] * 3
    assert sources.stat().st_mode & 0o7777 == 0o750


@pytest.mark.parametrize("label", ["WORDING only", "COMMAND TEXT only"])
def test_failing_diagnostics_do_not_change_the_summary_verdict_denominator(label):
    """Catches an optional diagnostic turning an unjudged effect into a counted failure."""
    assert RUN._only_unjudged(
        {
            "verdict": "UNVERIFIED",
            "required": ["effect"],
            "claims": {"effect": "UNVERIFIED", "hint": "FAIL"},
            "unjudged": {"effect": "receipt cannot be read"},
            "diagnostics": {"hint": label},
        }
    )


@needs_posix_bash
def test_next_turn_waits_for_a_peer_before_reading_fixture_sources(tmp_path):
    """Catches the turn program reading original sources without an exclusive runner lease."""
    import threading

    driver, _ = _driver(tmp_path, [])
    sources = tmp_path / "sources"
    sources.mkdir(mode=0o750)
    reference = sources / "reference.py"
    reference.write_text("kept", encoding="utf-8")
    driver.place = driver.place._replace(sources=sources)
    driver.call(driver.base)
    program = driver.place.stage / "next.py"
    with driver.source_read():
        program.write_text(
            "from pathlib import Path\n"
            f"assert Path({str(reference)!r}).read_text(encoding='utf-8') == 'kept'\n"
            + program.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    peer = source_process(sources)
    timer = None
    try:
        assert peer.stdout.readline().strip() == "sealed"

        def finish():
            peer.stdin.write("finish\n")
            peer.stdin.flush()

        # real time: release the peer while next_turn is blocked on its source lease.
        timer = threading.Timer(0.15, finish)
        timer.start()
        assert driver.next_turn() == {"end": True, "reason": "complete", "protocol_defect": False}
        output, error = peer.communicate(timeout=15)
        assert peer.returncode == 0, error
        assert json.loads(output)["isolation"][0][1] == "PASS"
    finally:
        if timer is not None:
            timer.join()
        if peer.poll() is None:
            peer.kill()
        peer.communicate(timeout=15)


@pytest.mark.parametrize("harness_name", ["codex", "claude-code"])
@pytest.mark.parametrize(
    "command",
    ["mkdir -p ../stage", "test -d ../stage", "ls -d ../stage", "stat ../stage", "touch ../stage"],
)
def test_metadata_and_write_operands_never_prove_content_reads(tmp_path, harness_name, command):
    """Catches a successful metadata check or write being counted as protected content."""
    driver, harness = _driver(tmp_path, [])
    harness.name = harness_name
    driver = Driver(driver.session, "Start.", driver.request, harness, driver.place)
    original = harness.call

    def call(*args):
        result = original(*args)
        done = subprocess.run(
            ["sh", "-c", command],
            cwd=driver.place.workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
        assert done.returncode == 0, done.stderr
        item = result.extras["native_sessions"][0]
        if harness_name == "codex":
            rows = harness.rows[result.extras["thread_id"]]
            event = _executed_command(command, driver.place.workspace)
            event["payload"]["item"]["aggregated_output"] = done.stdout + done.stderr
            _rows(Path(item["copy"]), [*rows, event])
        if harness_name == "claude-code":
            _rows(
                Path(item["copy"]),
                [
                    {
                        "type": "assistant",
                        "cwd": str(driver.place.workspace),
                        "message": {
                            "id": "answer",
                            "usage": {
                                "input_tokens": 1,
                                "cache_creation_input_tokens": 0,
                                "cache_read_input_tokens": 0,
                                "output_tokens": 1,
                            },
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "cmd",
                                    "name": "Bash",
                                    "input": {"command": command},
                                }
                            ],
                        },
                    },
                    {
                        "type": "user",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "cmd",
                                    "is_error": False,
                                    "content": done.stdout + done.stderr,
                                }
                            ]
                        },
                    },
                ],
            )
        return result

    harness.call = call
    result = driver.run()
    assert not result.extras.get("void"), result.extras
    assert result.extras["isolation_verdict"] == (
        "UNVERIFIED" if harness_name == "claude-code" else "PASS"
    )


@pytest.mark.parametrize("native_id", [False, True])
def test_cut_identical_commands_keep_the_external_request(tmp_path, native_id):
    """Catches a workspace completion consuming a same-text external request."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    external = tmp_path / "external"
    wrapper = {
        "type": "response_item",
        "payload": {
            "type": "custom_tool_call",
            "name": "exec",
            "call_id": "batch",
            "input": "await Promise.all([tools.exec_command({cmd:'cat answer.txt',workdir:"
            + json.dumps(str(external))
            + "}),tools.exec_command({cmd:'cat answer.txt',workdir:"
            + json.dumps(str(workspace))
            + "})]);",
        },
    }
    rows = [_meta("session"), wrapper, _executed_command("cat answer.txt", workspace)]
    rows[-1]["payload"]["item"]["aggregated_output"] = "WORKSPACE_MARKER"
    if native_id:
        # Direct native requests have an actual call id; command text cannot override it.
        rows[1] = {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": "external",
                "arguments": json.dumps({"cmd": "cat answer.txt", "workdir": str(external)}),
            },
        }
        rows.insert(
            2,
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "local",
                    "arguments": json.dumps({"cmd": "cat answer.txt", "workdir": str(workspace)}),
                },
            },
        )
        rows[-1]["payload"]["item"]["call_id"] = "local"
    item = _rows(tmp_path / "native.jsonl", rows)
    actions = [a for a in ActionLedger().add([item], "codex", workspace) if a["kind"] == "command"]
    assert [(a["cwd"], a["status"]) for a in actions] == [
        (str(external), "unknown"),
        (str(workspace), "ok"),
    ]
    from evals.session_evidence import isolation_residual

    residual = isolation_residual([], actions, workspace)
    assert residual == [{"command": "cat answer.txt", "paths": [str(external / "answer.txt")]}]


@pytest.mark.parametrize("identity", [None, "first", "second"])
def test_ambiguous_cut_requests_are_both_unresolved(tmp_path, identity):
    """Catches assigning one of two indistinguishable starts an arbitrary success."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    rows = [_meta("session")]
    rows.extend(
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "exec_command",
                "call_id": key,
                "arguments": json.dumps({"cmd": "cat answer.txt", "workdir": str(workspace)}),
            },
        }
        for key in ("first", "second")
    )
    rows.append(_executed_command("cat answer.txt", workspace))
    if identity is not None:
        rows[-1]["payload"]["item"]["call_id"] = identity
    item = _rows(tmp_path / "native.jsonl", rows)
    actions = ActionLedger().add([item], "codex", workspace)
    assert [a["status"] for a in actions] == {
        None: ["unknown", "unknown", "ok"],
        "first": ["ok", "unknown"],
        "second": ["unknown", "ok"],
    }[identity]


@pytest.mark.parametrize("label", ["COMMAND TEXT only", "WORDING only"])
@pytest.mark.parametrize("kept", [False, True])
def test_required_diagnostic_is_a_protocol_defect_before_any_grade(
    tmp_path, monkeypatch, label, kept
):
    """Catches an invalid diagnostic plan running effects and becoming a model FAIL."""
    fixtures = tmp_path / "evals/fixtures"
    fixture = fixtures / "session-example"
    fixture.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = workspace / "graded"
    plan = {
        "version": 1,
        "claims": [
            {
                "name": "effect",
                "risk": "observed state",
                "kind": "static",
                "command": [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
            },
            {
                "name": "hint",
                "risk": label + ": example",
                "required": True,
                "kind": "static",
                "command": [sys.executable, "-c", "raise SystemExit(1)"],
            },
        ],
    }
    (fixture / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    graders = tmp_path / "kept" if kept else None
    if graders is not None:
        graders.mkdir()
        (graders / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
        (fixture / "post.plan.json").write_text('{"version":1,"claims":[]}', encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    extra: dict[str, Any] = {}
    report = RUN.grade(
        "session-example",
        workspace,
        RUN.Left(None, "transcript", "answer"),
        (True, ""),
        extra,
        graders,
    )
    assert not marker.exists()
    assert extra["void"] == "protocol_defect" and extra["verdict"] == "UNVERIFIED"
    assert extra["claims"] == {} and "claims are not required" in report


@needs_posix_bash
def test_a_call_group_whose_members_all_exited_is_stopped_where_the_host_refuses_its_probe(
    monkeypatch,
):
    """Catches a refused group probe, as macOS gives for a group of exited, unreaped members,
    read as a failure to stop the call: the table shows no member running, so none is left."""
    from evals import processes

    def refused(group, sig):
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(processes.os, "killpg", refused)
    monkeypatch.setattr(processes, "_process_table", lambda: {4242: (1, "Z")})
    monkeypatch.setattr(processes.os, "getpgid", lambda pid: 4242)
    processes.stop_call_group(4242)


def test_dead_runner_keeps_sources_sealed_until_its_live_call_has_ended(tmp_path):
    """Catches SIGKILL releasing a runner's lock while its call can still read sources."""
    from evals.session_permissions import source_access

    root = tmp_path / "engine/evals/fixtures"
    root.mkdir(parents=True, mode=0o750)
    secret = root / "answer.txt"
    secret.write_text("PROTECTED_MARKER", encoding="utf-8")
    outcome = tmp_path / "outcome"
    child_code = (
        "import os,time\nfrom pathlib import Path\n"
        "print(os.getpid(), flush=True)\ntime.sleep(0.8)\n"
        f"source=Path({str(secret)!r})\n"
        "try:\n text=source.read_text(encoding='utf-8')\n"
        "except PermissionError:\n text='blocked'\n"
        f"Path({str(outcome)!r}).write_text(text, encoding='utf-8')\n"
    )
    script = (
        "import sys\nfrom pathlib import Path\n"
        "from evals.session_permissions import sealed_sources\n"
        "from evals.watch import watched_command\n"
        "sent=[]\n"
        "def poll(output):\n"
        " if output().strip() and not sent:\n"
        "  sent.append(True)\n  print(output().strip(), flush=True)\n"
        f"with sealed_sources(Path({str(root)!r}), {{}}):\n"
        f" watched_command([sys.executable,'-c',{child_code!r}], "
        "timeout=5, poll=poll, interval=0.01)\n"
    )
    runner = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    reader = None
    try:
        import select

        assert runner.stdout is not None
        assert select.select([runner.stdout], [], [], 10)[0]
        pid = int(runner.stdout.readline())
        runner.kill()
        runner.wait(timeout=10)
        assert root.stat().st_mode & 0o7777 == 0
        os.kill(pid, 0)
        reader = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from pathlib import Path\nfrom evals.session_permissions import source_access\n"
                + f"root=Path({str(root)!r})\nwith source_access(root):\n"
                " print((root/'answer.txt').read_text(encoding='utf-8'))\n",
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        with pytest.raises(subprocess.TimeoutExpired):
            reader.wait(timeout=0.15)
        assert root.stat().st_mode & 0o7777 == 0
        output, error = reader.communicate(timeout=10)
        assert reader.returncode == 0, error
        assert output.strip() == "PROTECTED_MARKER"
        if os.geteuid() != 0:
            assert outcome.read_text(encoding="utf-8") == "blocked"
        assert root.stat().st_mode & 0o7777 == 0o750
    finally:
        if runner.poll() is None:
            runner.kill()
        runner.communicate(timeout=10)
        if reader is not None:
            if reader.poll() is None:
                reader.kill()
            reader.communicate(timeout=10)
        with source_access(root):
            pass


@needs_posix_bash
def test_two_driver_processes_exclude_peer_seal_wait_from_active_time_and_budget(tmp_path):
    """Catches a peer's 0.7-second call timing out a fast call with a 0.35-second budget."""
    root = tmp_path / "engine/evals/fixtures"
    root.mkdir(parents=True, mode=0o750)
    (root / "answer.txt").write_text("kept", encoding="utf-8")
    script = """
import json,sys,time
from pathlib import Path
from tests.test_long_eval_protocol import _driver
folder, sources = Path(sys.argv[1]), Path(sys.argv[2])
folder.mkdir()
delay=float(sys.argv[3])
print('prepared', flush=True)
sys.stdin.readline()
driver,harness = _driver(folder, [], seconds=0.35 if delay<0.1 else 5)
driver.place=driver.place._replace(sources=sources, forbidden=(sources,))
original=harness.call
def call(*args):
    assert sources.stat().st_mode & 0o7777 == 0
    print('calling', flush=True)
    time.sleep(delay)
    return original(*args)
harness.call=call
# Exercise the call and the following budget decision without timing guard-process startup.
result=driver.call(driver.base)
driver.following(result)
print(json.dumps({**driver.extras, 'active_seconds': driver.active}), flush=True)
"""

    def start(name, delay):
        return subprocess.Popen(
            [sys.executable, "-c", script, str(tmp_path / name), str(root), str(delay)],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    slow, fast, alone = start("slow", 0.7), start("fast", 0.03), None
    try:
        for child in (slow, fast):
            assert child.stdout.readline().strip() == "prepared"
        slow.stdin.write("start\n")
        slow.stdin.flush()
        assert slow.stdout.readline().strip() == "calling"
        fast.stdin.write("start\n")
        fast.stdin.flush()
        output, error = fast.communicate(timeout=15)
        assert fast.returncode == 0, error
        concurrent = json.loads(output.splitlines()[-1])
        output, error = slow.communicate(timeout=15)
        assert slow.returncode == 0, error
        assert json.loads(output.splitlines()[-1])["isolation_verdict"] == "PASS"
        alone = start("alone", 0.03)
        assert alone.stdout.readline().strip() == "prepared"
        alone.stdin.write("start\n")
        alone.stdin.flush()
        output, error = alone.communicate(timeout=15)
        assert alone.returncode == 0, error
        solo = json.loads(output.splitlines()[-1])
        assert concurrent["active_seconds"] < 0.25
        assert abs(concurrent["active_seconds"] - solo["active_seconds"]) < 0.15
        assert concurrent["seal_wait_seconds"] > 0.3
        assert concurrent.get("stopped") is solo.get("stopped") is None
        assert concurrent["isolation_verdict"] == solo["isolation_verdict"] == "PASS"
        assert root.stat().st_mode & 0o7777 == 0o750
    finally:
        for child in (slow, fast, alone):
            if child is not None:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=15)


@needs_posix_bash
def test_idle_peer_stage_and_source_state_are_unreadable_to_another_call(tmp_path):
    """Catches a known sibling stage or the seal state exposing grading inputs."""
    from evals.session_permissions import SourceLease

    sources = tmp_path / "engine/evals/fixtures"
    sources.mkdir(parents=True)
    (sources / "answer.txt").write_text("PROTECTED_MARKER", encoding="utf-8")
    places = []
    for name in ("first", "second"):
        folder = tmp_path / name
        folder.mkdir()
        driver, harness = _driver(folder, [])
        driver.place = driver.place._replace(sources=sources, forbidden=(sources,))
        places.append((driver, harness))
    peer, _ = places[0]
    (peer.place.stage / "answer.txt").write_text("PROTECTED_MARKER", encoding="utf-8")
    assert peer.run().extras["isolation_verdict"] == "PASS"
    assert peer.place.stage.stat().st_mode & 0o7777 == 0
    lease = SourceLease(sources)
    state = lease.record
    lease.release()
    driver, harness = places[1]
    original = harness.call

    def call(*args):
        for path in (state, peer.place.stage / "answer.txt"):
            assert (state if path == state else peer.place.stage).stat().st_mode & 0o7777 == 0
            if os.geteuid() != 0:
                with pytest.raises(PermissionError):
                    path.read_text(encoding="utf-8")
        return original(*args)

    harness.call = call
    assert driver.run().extras["isolation_verdict"] == "PASS"
    assert state.stat().st_mode & 0o7777 == 0o600


@needs_posix_bash
@pytest.mark.parametrize("signal_exit", [False, True])
def test_sealed_call_gate_preserves_stdout_and_actual_exit_status(tmp_path, signal_exit):
    """Catches the recovery wrapper converting a signal into a normal numeric exit."""
    from evals.session_permissions import sealed_sources

    sources = tmp_path / "engine/evals/fixtures"
    sources.mkdir(parents=True)
    script = "import os,signal\nprint('output', flush=True)\n" + (
        "os.kill(os.getpid(), signal.SIGTERM)\n" if signal_exit else "raise SystemExit(7)\n"
    )
    extra: dict[str, Any] = {}
    with sealed_sources(sources, extra):
        result = watched_command([sys.executable, "-c", script], timeout=5)
    assert result.stdout == "output\n"
    assert result.returncode == (-signal.SIGTERM if signal_exit else 7)
    assert result.stopped is None
    assert not extra.get("void")


@needs_posix_bash
def test_recovery_has_the_original_mode_if_sealing_is_interrupted(tmp_path, monkeypatch):
    """Catches losing the restoration mode when a runner dies between sealing writes."""
    from evals.session_permissions import SourceLease, sealed_sources, source_access

    sources = tmp_path / "engine/evals/fixtures"
    sources.mkdir(parents=True, mode=0o750)
    original = SourceLease.write
    writes = []

    def write(lease, state):
        if state.get("active"):
            writes.append(True)
            if len(writes) == 2:
                raise RuntimeError("interrupted seal initialization")
        return original(lease, state)

    monkeypatch.setattr(SourceLease, "write", write)
    with (
        pytest.raises(RuntimeError, match="interrupted seal initialization"),
        sealed_sources(sources, {}),
    ):
        pytest.fail("the call must not start after incomplete sealing")
    with source_access(sources):
        assert sources.stat().st_mode & 0o7777 == 0o750
