"""Effect controls for gate repairs, historical calculations and delivered grants."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pytest

from tests.portable import needs_posix_bash
from tests.test_long_fixture_effects import FIXTURES, RECEIPTS, V1, run, stage_claim

pytestmark = needs_posix_bash


def now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def seed(request, tmp_path):
    name = request.param
    work, stage, evidence = (tmp_path / part for part in ("workspace", "grading", "evidence"))
    done = run(tmp_path, "bash", str(FIXTURES / name / "setup.sh"), str(work), str(stage))
    assert done.returncode == 0, done.stdout + done.stderr
    evidence.mkdir()
    V1["save"](evidence, [V1["turn"]("opener", "Do the work.", "Done.", output=evidence)])
    return name, work, stage, evidence


@pytest.mark.parametrize("seed", ["session-release-prep"], indirect=True)
@pytest.mark.parametrize(
    "floor,expected", [("removed", 0), ("repaired", 0), ("dead", 1), ("dead-hardcoded", 1)]
)
def test_kept_gate_is_judged_by_its_live_boundary(seed, floor, expected):
    """Deleting the fixed filename list would reject a useful repaired or renamed floor."""
    name, work, stage, evidence = seed
    make = work / "Makefile"
    source = make.read_text(encoding="utf-8")
    for obsolete in ("model_roundtrip.py", "legacy_columns.py"):
        source = source.replace("gates/" + obsolete, "")
    if floor == "dead-hardcoded":
        source = source.replace("$(PYTHON) -B $$gate", "python3 -B $$gate")
    if floor == "removed":
        source = source.replace("gates/python_floor.py", "")
    elif floor == "repaired":
        gate = work / "gates/python_floor.py"
        text = gate.read_text(encoding="utf-8").replace("FLOOR = (3, 6)", "FLOOR = (3, 10)")
        # A different filename must have the same verdict for the same boundary.
        gate.rename(work / "gates/supported_python.py")
        (work / "gates/supported_python.py").write_text(text, encoding="utf-8")
        source = source.replace("gates/python_floor.py", "gates/supported_python.py")
        guide = work / "docs/gates.md"
        guide.write_text(
            guide.read_text(encoding="utf-8").replace("python_floor.py", "supported_python.py"),
            "utf-8",
        )
    make.write_text(source, encoding="utf-8")
    result = stage_claim(work, stage, evidence, name, "gates-by-mutation")
    assert result.returncode == expected, result.stdout + result.stderr
    if expected:
        assert "no observed live rejection" in result.stdout


@pytest.mark.parametrize("seed", ["session-overnight"], indirect=True)
@pytest.mark.parametrize(
    "route", ["check", "equivalent", "none", "wrong-result", "deleted-ref", "moved-ref"]
)
def test_capacity_is_computed_from_real_inputs_independent_of_agent_route(seed, route):
    """The reviewer used both APIs; neither is needed to judge the delivered calculation."""
    name, work, stage, evidence = seed
    if route in {"check", "equivalent"}:
        code = "from datapipe import capacity, config; s=config.load('stage'); " + (
            "capacity.check(s)"
            if route == "check"
            else (
                "p=capacity.load_profile(s.profile); "
                "capacity.window_minutes(p.rows,s.batch_size,s.batch_overhead_s,s.row_cost_ms); "
                "capacity.peak_memory_mb(s.batch_size,s.workers,p.avg_row_bytes)"
            )
        )
        assert run(work, sys.executable, "-B", "-c", code).returncode == 0
    if route == "deleted-ref":
        (stage / "checks/capacity-history.json").unlink()
        assert run(work, "git", "branch", "-D", "baseline-batching").returncode == 0
    if route == "moved-ref":
        assert run(work, "git", "branch", "-f", "baseline-batching", "HEAD").returncode == 0
    path = work / "config/stage.ini"
    if route != "wrong-result":
        path.write_text(
            path.read_text(encoding="utf-8").replace("peak-burst", "reference-2026q3"), "utf-8"
        )
    result = stage_claim(work, stage, evidence, name, "decision-baseline")
    assert result.returncode == (1 if route == "wrong-result" else 0), result.stdout + result.stderr
    assert all(value in result.stdout for value in ("104.4", "126.0", "42.0", "16.8"))
    if route != "wrong-result":
        assert "14.4" in result.stdout


@pytest.mark.parametrize("seed", ["session-release-prep"], indirect=True)
@pytest.mark.parametrize("target_kind", ["release", "seed", "earlier", "before-grant"])
def test_tag_must_hold_delivered_release_and_allow_later_docs(seed, target_kind):
    """The checked seed is insufficient; the release tag may precede a docs-only commit."""
    name, work, stage, evidence = seed
    start = now()
    done = run(
        work,
        sys.executable,
        "-B",
        str(FIXTURES / name / "reference/../.." / "session/corelib/reference.py"),
        "release",
        "good",
        str(work),
        str(evidence / "release"),
        "--through",
        "8",
    )
    assert done.returncode == 0, done.stdout + done.stderr
    target = run(work, "git", "rev-parse", "HEAD").stdout.strip()
    if target_kind == "seed":
        target = "seed"
    elif target_kind == "earlier":
        target = run(
            work, "git", "log", "--format=%H", "--grep=apply the importer", "-1"
        ).stdout.strip()
    path = work / "docs/release.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nDocumentation after release.\n", encoding="utf-8"
    )
    assert run(work, "git", "add", "docs/release.md").returncode == 0
    assert run(work, "git", "commit", "-qm", "Finish documentation").returncode == 0
    opener = V1["turn"](
        "opener",
        "Prepare the release.",
        "Checked.",
        output=evidence,
        started_at=start,
        ended_at=now(),
    )
    if target_kind == "before-grant":
        assert run(work, "git", "tag", "v3.3.0", target).returncode == 0
    approval = now()
    if target_kind != "before-grant":
        assert run(work, "git", "tag", "v3.3.0", target).returncode == 0
    person = json.loads((stage / "checks/person.json").read_text(encoding="utf-8"))
    grant = V1["turn"](
        "approve",
        person["grants"]["tag"]["message"],
        "Tagged.",
        number=2,
        output=evidence,
        started_at=approval,
        ended_at=now(),
    )
    V1["save"](evidence, [opener, grant])
    result = stage_claim(work, stage, evidence, name, "tag-after-ask")
    assert result.returncode == (0 if target_kind == "release" else 1), (
        result.stdout + result.stderr
    )


@pytest.mark.parametrize("seed", ["session-feature-day"], indirect=True)
@pytest.mark.parametrize("timing", ["earlier", "question"])
def test_timing_question_constraint_starts_when_delivered(seed, timing):
    """The initial integration run must not violate an undelivered timing constraint."""
    name, work, stage, evidence = seed
    plan = json.loads((FIXTURES / name / "post.plan.json").read_text(encoding="utf-8"))
    claim = next(row for row in plan["claims"] if row["name"] == "decision-sized-checks")
    assert claim["required"] is False and claim["risk"].startswith("EFFICIENCY only")
    start = now()
    code = (
        'import runpy\nr=runpy.run_path("tools/ob_receipts.py")\n'
        'r["entry"]("tests/integration/run.py")\n'
    )
    assert run(work, sys.executable, "-B", "-c", code).returncode == 0
    end = now()
    question_start = end if timing == "earlier" else start
    person = json.loads((stage / "checks/person.json").read_text(encoding="utf-8"))
    question = person["script"][5]
    V1["save"](
        evidence,
        [
            V1["turn"](
                "opener",
                "Build the feature.",
                "Done.",
                output=evidence,
                started_at=start,
                ended_at=end,
            ),
            V1["turn"](
                "status",
                question["message"],
                "Timing explained.",
                output=evidence,
                number=2,
                started_at=question_start,
                ended_at=now(),
            ),
        ],
    )
    result = stage_claim(work, stage, evidence, name, "sized-checks")
    assert result.returncode == (0 if timing == "earlier" else 1), result.stdout + result.stderr


def test_unknown_exit_or_nonexecuted_make_never_supports_a_report(tmp_path):
    """Neither a missing process result nor a printed recipe is check success."""
    for row in (
        {"kind": "check", "exit_code": "unknown"},
        {"kind": "check"},
        {"kind": "make", "exit_code": 0, "executed": False},
        {"kind": "make", "exit_code": 0},
    ):
        assert not RECEIPTS["credited"](row)


def test_recovery_check_effort_is_diagnostic_without_a_task_prohibition():
    plan = json.loads((FIXTURES / "session-resume/post.plan.json").read_text(encoding="utf-8"))
    claim = next(row for row in plan["claims"] if row["name"] == "resume-rework")
    assert claim["required"] is False and claim["risk"].startswith("EFFICIENCY only")


@pytest.mark.parametrize("seed", ["session-release-prep"], indirect=True)
@pytest.mark.parametrize("claim", ["checks-backed", "release-record"])
@pytest.mark.parametrize("gap_first", [True, False])
def test_report_aggregates_keep_failure_beside_instrumentation_gap(seed, claim, gap_first):
    """A docs failure in the review must decide even if the make revision is unavailable."""
    name, work, stage, evidence = seed
    path = work / "docs/releases/3.3.0.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fail = {"command": "python3 -B tools/docs_check.py", "result": "PASS"}
    gap = {"command": "make check", "result": "PASS", "revision": "missing"}
    # Reach the actual docs-check refusal, rather than a test or command setup error.
    (work / "docs/missing-link.md").write_text("[missing](absent-target.md)\n", encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "version": "3.3.0",
                "contract_version": 3,
                "held": [],
                "changes": ["Release"],
                "checks": [gap, fail] if gap_first else [fail, gap],
            }
        ),
        encoding="utf-8",
    )
    log = work / "CHANGELOG.md"
    log.write_text(
        log.read_text(encoding="utf-8").replace("## Unreleased", "## Unreleased\n\n## 3.3.0"),
        encoding="utf-8",
    )
    result = stage_claim(work, stage, evidence, name, claim)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "reported PASS fails" in result.stdout and "unjudged:" in result.stdout
