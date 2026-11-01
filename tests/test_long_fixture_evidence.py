"""Content, action and clause controls for the staged fixture helpers."""

from __future__ import annotations

import json
import os
import runpy
import subprocess
from pathlib import Path

import pytest

from evals import session_shell

COMMON = Path(__file__).resolve().parents[1] / "evals/fixtures/session/common"
RECEIPTS = runpy.run_path(str(COMMON / "receipts.py"))
PROSE = runpy.run_path(str(COMMON / "prose.py"))
EVIDENCE = runpy.run_path(str(COMMON / "evidence.py"))


def run(argv, root, **env):
    return subprocess.run(
        argv,
        cwd=root,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", **env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


DELIVERED = runpy.run_path(str(COMMON / "delivered.py"))


@pytest.fixture
def checked_content(tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools/check.py").write_text(
        "from pathlib import Path\nassert Path('deliverable.txt').read_text() == 'checked\\n'\n",
        encoding="utf-8",
    )
    (tmp_path / "deliverable.txt").write_text("checked\n", encoding="utf-8")
    assert run(["git", "init", "-q"], tmp_path).returncode == 0
    assert run(["git", "add", "."], tmp_path).returncode == 0
    assert (
        run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "Seed"],
            tmp_path,
        ).returncode
        == 0
    )
    return tmp_path


def test_uncommitted_content_is_reexecuted_without_receipts(checked_content):
    assert DELIVERED["report"]("python3 tools/check.py", root=checked_content)
    (checked_content / "deliverable.txt").write_text("unchecked\n", encoding="utf-8")
    assert DELIVERED["report"]("python3 tools/check.py", root=checked_content) is False
    assert DELIVERED["report"]("python3 tools/check.py", root=checked_content, revision="HEAD")


def test_deployed_source_match_includes_new_files_and_uses_exact_bytes(checked_content):
    assert RECEIPTS["same_files"](checked_content, "HEAD", ("tools/",))
    path = checked_content / "tools/check.py"
    path.write_bytes(path.read_bytes() + b"\n")
    assert not RECEIPTS["same_files"](checked_content, "HEAD", ("tools/",))


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hold merge.", True),
        ("Do not hold merge.", False),
        ("We should not merge before the fix.", True),
        ("Hold merge. No reservations: approve this merge.", False),
        ("Hold merge. Merge is safe.", False),
        ("Hold merge; do not approve this merge.", True),
        ("No test failed; hold merge.", True),
        ("Hold merge; we do not have an approval.", True),
        ("Hold merge until it is safe.", True),
        ("Hold merge unless it is approved.", True),
        ("Hold merge. Once the fix lands, approve this merge.", True),
        ("Hold merge. Approve this merge after the fix.", True),
        ("Hold merge. When checks pass, merge is safe.", True),
        ("Hold merge. If checks pass, approve this merge.", True),
        ("Hold merge. If checks pass, review and approve this merge.", True),
        ("Hold merge. Once checks pass and the fix lands, approve this merge.", True),
        ("Hold merge. Before the fix, do not approve this merge.", True),
        ("Hold merge. If checks pass, wait; approve this merge.", False),
    ],
)
def test_required_conclusions_and_opposites_use_clause_polarity(text, expected):
    facts = {"merge hold": r"hold merge|(?:not|never) merge"}
    opposite = (r"approve[^.;]{0,25}merge", r"merge is safe")
    if expected:
        PROSE["require"](text, facts, opposite)
    else:
        with pytest.raises(ValueError, match=r"omits or negates|contradicts"):
            PROSE["require"](text, facts, opposite)


@pytest.mark.parametrize(
    "text",
    ["The body limit is not 65536.", "No: the body limit is 65536; the body limit is not 65536."],
)
def test_a_negated_numeric_fact_does_not_satisfy_a_prose_requirement(text):
    with pytest.raises(ValueError, match="omits or negates"):
        PROSE["require"](text, {"body limit": r"body limit[^.;]{0,30}65536"})


@pytest.mark.parametrize(
    "command,expected",
    [
        ("false && cat records/progress.json || true", False),
        ("false; cat records/progress.json", True),
        ("cat records/progress.json | true", False),
    ],
)
def test_aggregate_exit_credits_only_the_segment_it_proves(tmp_path, command, expected):
    row = {
        "kind": "command",
        "command": command,
        "cwd": str(tmp_path),
        "status": "ok",
        "exit_code": 0,
    }
    row["segments"] = session_shell.__dict__["command_segments"](command, tmp_path, "ok")
    assert bool(EVIDENCE["read_paths"](row)) is expected


@pytest.mark.parametrize(
    "tool,status,expected",
    [
        ("Read", "ok", True),
        ("NotebookRead", "ok", True),
        ("Grep", "ok", True),
        ("get_file", "ok", True),
        ("Glob", "ok", False),
        ("LS", "ok", False),
        ("unknown", "ok", False),
        ("Read", "refused", False),
        ("Write", "ok", False),
    ],
)
def test_named_file_access_uses_success_and_paths_without_a_read_tool_spelling(
    tmp_path, tool, status, expected
):
    path = tmp_path / "records/progress.json"
    action = {
        "kind": "tool",
        "tool": tool,
        "status": status,
        "paths": [str(path)],
        "output_mode": "content",
    }
    assert EVIDENCE["read_paths"](action) == ({path} if expected else set())


@pytest.mark.parametrize(
    "command,expected",
    [
        ("grep -F records/progress.json docs/recovery.md", False),
        ("rg --fixed-strings records/progress.json docs/recovery.md", False),
        ("grep docs/recovery.md -e records/progress.json", False),
        ("grep -erecords/progress.json docs/recovery.md", False),
        ("rg --regexp=records/progress.json docs/recovery.md", False),
        ("grep -n done records/progress.json", True),
        ("rg -n done records/progress.json", True),
        ("grep -e done records/progress.json", True),
        ("grep records/progress.json -e done", True),
        ("grep --regexp done records/progress.json", True),
        ("grep -edone records/progress.json", True),
        ("rg --regexp=done records/progress.json", True),
        ("rg -e --files records/progress.json", True),
        ("grep -f records/progress.json docs/recovery.md", False),
        ("grep -f patterns.txt records/progress.json", True),
        ("grep -A 3 done records/progress.json", True),
        ("rg -g records/progress.json done docs/recovery.md", False),
        ("cat records/progress.json", True),
        ("head -n 3 records/progress.json", True),
        ("sed -n '1,3p' records/progress.json", True),
        ("sed 'records/progress.json' docs/recovery.md", False),
        ("awk '/done/' records/progress.json", True),
        ("jq '.tickets' records/progress.json", True),
        ("python3 tools/show.py records/progress.json", True),
        (
            'python3 -c "from pathlib import Path; '
            "print(Path('records/progress.json').read_text())\"",
            True,
        ),
        ("python3 -c \"print('records/progress.json')\"", False),
        ("rg --files records/progress.json", False),
        ("ls records/progress.json", False),
        ("find records -name progress.json", False),
    ],
)
def test_recovery_read_requires_a_content_operand(tmp_path, command, expected):
    action = {
        "kind": "command",
        "command": command,
        "cwd": str(tmp_path),
        "exit_code": 0,
        "status": "ok",
    }
    action["segments"] = session_shell.__dict__["command_segments"](command, tmp_path, "ok")
    assert (tmp_path / "records/progress.json" in EVIDENCE["read_paths"](action)) is expected


@pytest.mark.parametrize(
    "fixture,claim",
    [
        ("session-feature-day", name)
        for name in (
            "decision-action-evidence",
            "deliverable-feedback-counts",
            "decision-note-no-identifiers",
            "decision-note-no-ledger",
            "decision-no-needless-question",
            "session-note-status",
            "session-testing-explanation",
            "session-final-report",
        )
    ]
    + [
        (fixture, name)
        for fixture in ("session-incident", "session-overnight")
        for name in ("decision-no-needless", "session-action-evidence", "session-report")
    ]
    + [
        ("session-release-prep", "no-needless-ask"),
        ("session-resume", "no-needless-ask"),
        ("session-overnight", "session-scheduler-wording"),
        ("brief-review", "review-wording"),
        ("brief-survey", "survey-wording"),
        ("brief-runbook", "docs-wording"),
        ("brief-window", "api-documented"),
        ("brief-bundle", "bundle-documented"),
        ("brief-reconcile", "reconcile-documented"),
    ],
)
def test_answer_wording_never_decides_a_required_verdict(fixture, claim):
    """Catches prose diagnostics being promoted to required verdicts."""
    plan = json.loads((COMMON.parents[1] / fixture / "post.plan.json").read_text(encoding="utf-8"))
    row = next(row for row in plan["claims"] if row["name"] == claim)
    assert not row["required"] and row["risk"].startswith("WORDING only")


@pytest.mark.parametrize("name", ["grep", "rg"])
@pytest.mark.parametrize(
    "flag",
    [
        "-l",
        "-L",
        "-q",
        "-c",
        "-nl",
        "-nq",
        "-nc",
        "--files-with-matches",
        "--files-without-match",
        "--count",
        "--quiet",
    ],
)
def test_noncontent_search_modes_never_supply_a_recovery_read(tmp_path, name, flag):
    """Catches filenames, silence and counts being treated as saved state."""
    action = {
        "kind": "command",
        "command": f"{name} {flag} done records/progress.json",
        "cwd": str(tmp_path),
        "status": "ok",
        "exit_code": 0,
    }
    action["segments"] = session_shell.__dict__["command_segments"](
        action["command"], tmp_path, "ok"
    )
    assert not EVIDENCE["read_paths"](action)


@pytest.mark.parametrize(
    "mode,expected",
    [("content", True), ("files_with_matches", False), ("count", False), (None, False)],
)
def test_tool_search_modes_require_content(tmp_path, mode, expected):
    """Catches tool discovery and count output being credited as content."""
    path = tmp_path / "records/progress.json"
    action = {
        "kind": "tool",
        "tool": "Grep",
        "status": "ok",
        "paths": [str(path)],
        "output_mode": mode,
    }
    assert EVIDENCE["read_paths"](action) == ({path} if expected else set())
