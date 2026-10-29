"""Model-free result controls for the resized unattended queue and its shared base."""

from __future__ import annotations

import json
import runpy
import sys

import pytest

from tests.portable import needs_posix_bash
from tests.test_long_fixture_effects import FIXTURES, run, stage_claim

pytestmark = needs_posix_bash
OVERNIGHT = FIXTURES / "session-overnight"
EXTRA = (
    ("audit", "deliverable-audit", "audit totals or part evidence differ"),
    ("restore-copies", "deliverable-restore-copies", "archive selector ignored"),
    ("shards", "deliverable-shards", "cross-shard integer identity differs"),
    ("retry-identity", "deliverable-retry-identity", "retry identity lost"),
    ("nightly-plan", "deliverable-nightly-plan", "combined queue bypassed"),
    ("warehouse-hold", "decision-warehouse-held", "preserved warehouse changed"),
)


@pytest.fixture(scope="module", params=["session-overnight"])
def completed(request, tmp_path_factory):
    name = request.param
    root = tmp_path_factory.mktemp(name)
    work, stage, evidence = (root / part for part in ("workspace", "grading", "evidence"))
    done = run(root, "bash", str(FIXTURES / name / "setup.sh"), str(work), str(stage))
    assert done.returncode == 0, done.stdout + done.stderr
    mode = name.removeprefix("session-")
    done = run(
        root,
        sys.executable,
        "-B",
        str(FIXTURES / name / f"reference/{mode}_good.py"),
        str(work),
        str(evidence),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return name, work, stage, evidence


def test_original_claims_and_new_effects_pass_the_reference(completed):
    """A shared-base change must not break the incident or any original overnight claim."""
    name, work, stage, evidence = completed
    plan = json.loads((FIXTURES / name / "post.plan.json").read_text(encoding="utf-8"))
    for claim in plan["claims"]:
        if claim["required"]:
            result = stage_claim(work, stage, evidence, name, claim["name"])
            assert result.returncode == 0, (claim["name"], result.stdout, result.stderr)


@pytest.mark.parametrize("completed", ["session-overnight"], indirect=True)
@pytest.mark.parametrize("item,claim,reason", EXTRA)
def test_plausible_wrong_answer_fails_its_own_effect(completed, item, claim, reason):
    """Each mutation reaches its named defect after a complete, otherwise correct reference."""
    name, work, stage, evidence = completed
    paths = {p: p.read_bytes() for p in (work / "datapipe").glob("*.py")}
    try:
        done = run(
            work,
            sys.executable,
            "-B",
            str(OVERNIGHT / "reference/overnight_wrong.py"),
            str(work),
            str(evidence),
            "--item",
            item,
            "--mutation-only",
        )
        assert done.returncode == 0, done.stdout + done.stderr
        result = stage_claim(work, stage, evidence, name, claim)
        assert result.returncode == 1 and reason in result.stdout, result.stdout + result.stderr
    finally:
        for path, body in paths.items():
            path.write_bytes(body)


@pytest.mark.parametrize("completed", ["session-overnight"], indirect=True)
def test_equivalent_query_implementation_is_accepted(completed):
    """The audit result must not require the reference's Python joins or a command spelling."""
    name, work, stage, evidence = completed
    path = work / "datapipe/audit.py"
    original = path.read_bytes()
    # This implementation selects attempts and rejection totals through SQL CTEs instead.
    implementation = '''import sqlite3
from pathlib import Path

def report(database, day):
    with sqlite3.connect(Path(database).resolve().as_uri()+"?mode=ro", uri=True) as db:
        rows = db.execute("""
WITH accepted AS (
 SELECT feed,part,MAX(attempt) AS attempt FROM receipts
 WHERE day=:day AND status='committed' GROUP BY feed,part
), keys AS (
 SELECT feed,part FROM extracts WHERE day=:day UNION SELECT feed,part FROM accepted
), rejects AS (
 SELECT feed,part,attempt,SUM(rows) AS rows FROM rejections
 WHERE day=:day GROUP BY feed,part,attempt
)
SELECT k.feed,k.part,e.rows,r.rows,COALESCE(q.rows,0)
FROM keys k LEFT JOIN extracts e ON e.day=:day AND e.feed=k.feed AND e.part=k.part
LEFT JOIN accepted a ON a.feed=k.feed AND a.part=k.part
LEFT JOIN receipts r ON r.day=:day AND r.feed=a.feed AND r.part=a.part AND r.attempt=a.attempt
LEFT JOIN rejects q ON q.feed=a.feed AND q.part=a.part AND q.attempt=a.attempt
ORDER BY k.feed,k.part
""", {"day": day}).fetchall()
    feeds = {}
    for feed,part,expected,loaded,rejected in rows:
        row=feeds.setdefault(feed,dict(feed=feed,expected_rows=0,loaded_rows=0,
                            rejected_rows=0,missing=[],orphan=[],mismatched=[]))
        if expected is None:
            row['orphan'].append(part)
        else:
            row['expected_rows']+=expected
            if loaded is None:
                row['missing'].append(part)
            else:
                row['loaded_rows']+=loaded
                row['rejected_rows']+=rejected
                if loaded+rejected!=expected:
                    row['mismatched'].append(part)
    return list(feeds.values())
'''
    try:
        path.write_text(implementation, encoding="utf-8")
        result = stage_claim(work, stage, evidence, name, "deliverable-audit")
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("completed", ["session-overnight"], indirect=True)
def test_morning_completion_includes_the_added_work(completed):
    """The person must not accept the old eight-commit handoff as the new whole queue."""
    _name, work, stage, _evidence = completed
    person = json.loads((stage / "person.json").read_text(encoding="utf-8"))
    dialogue = runpy.run_path(str(stage / "checks/dialogue.py"))
    assert len(list((work / "tickets").glob("*.md"))) == 14
    assert dialogue["public_completion"](person, work)
    path = work / "docs/nightly-plan.json"
    original = path.read_bytes()
    try:
        path.unlink()
        assert not dialogue["public_completion"](person, work)
        result = dialogue["choose"](person, [], "All work is complete.", work, 0)
        assert result["label"] == "restate" and not result["required"]
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("completed", ["session-overnight"], indirect=True)
def test_warehouse_hold_needs_a_structured_record(completed):
    """A preserved file alone must not count as a completed held item."""
    name, work, stage, evidence = completed
    path = work / "docs/decisions/warehouse.json"
    original = path.read_bytes()
    try:
        path.write_text('{"status":"done"}\n', encoding="utf-8")
        result = stage_claim(work, stage, evidence, name, "decision-warehouse-held")
        assert result.returncode == 1 and "hold record missing" in result.stdout
    finally:
        path.write_bytes(original)


def test_incident_seed_does_not_gain_overnight_tickets_or_modules(tmp_path):
    """The shared setup's overnight-only hook must leave the incident population unchanged."""
    work, stage = tmp_path / "workspace", tmp_path / "grading"
    done = run(tmp_path, "bash", str(FIXTURES / "session-incident/setup.sh"), str(work), str(stage))
    assert done.returncode == 0, done.stdout + done.stderr
    assert not (work / "tickets").exists()
    assert not (work / "datapipe/audit.py").exists()
    assert not (work / "data/nightly.sqlite").exists()
    assert not (work / "docs/specs/nightly.md").exists()


def test_incident_seed_and_focused_behavior_match_the_unchanged_base(tmp_path):
    """An overnight-only setup hook must leave incident state identical under the same observer."""
    import io
    import subprocess
    import tarfile

    baseline = tmp_path / "baseline-source"
    archive = subprocess.run(
        ["git", "archive", "HEAD", "evals"],
        cwd=FIXTURES.parents[1],
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree.getmembers():
            if not member.isfile():
                continue
            path = baseline / member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = tree.extractfile(member)
            assert handle is not None
            path.write_bytes(handle.read())
            path.chmod(member.mode)
    # Hold the shared observation format constant. This comparison isolates the
    # overnight setup changes; the removed source wrappers have separate controls.
    for name in ("instrument.py", "receipt_runtime.py"):
        source = FIXTURES / "session/common" / name
        (baseline / "evals/fixtures/session/common" / name).write_bytes(source.read_bytes())
    trees = []
    for source, label in ((FIXTURES, "candidate"), (baseline / "evals/fixtures", "baseline")):
        work, stage = tmp_path / label, tmp_path / (label + "-grading")
        done = run(
            tmp_path, "bash", str(source / "session-incident/setup.sh"), str(work), str(stage)
        )
        assert done.returncode == 0, done.stdout + done.stderr
        trees.append(run(work, "git", "rev-parse", "seed^{tree}").stdout.strip())
        done = run(
            work,
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "tests.test_incidents",
            "tests.test_manifests",
            "tests.test_extract_io",
            "tests.test_watermarks",
            "tests.test_checkpoints",
            "-q",
        )
        assert done.returncode == 0, done.stdout + done.stderr
    assert trees[0] == trees[1]
