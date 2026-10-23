"""A claim whose check could not judge (a missing toolchain, the check's own time or resource
limit) is recorded apart from a failure: the check exits `UNJUDGED_EXIT` with an `unjudged:` line,
the meta lists it under `unjudged`, and the summary and the panel leave it out of the denominators
and list it per arm. An UNVERIFIED claim with no such line still counts as not passing. No model is
called."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.eval_helpers import FIXTURES, RUN, load, transcript
from tests.portable import needs_posix_bash

PANEL = load("eval_panel_unjudged", "evals/panel.py")
UNJUDGED_CONTRACT = {"no_tests_exit": 3, "when_none": "UNVERIFIED"}


def _claim(name: str, script: str, **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "risk": f"{name} does not hold",
        "kind": "static",
        "required": True,
        "command": ["sh", "-c", script],
        **extra,
    }


@needs_posix_bash
def test_a_check_that_could_not_judge_is_recorded_as_unjudged(tmp_path: Path) -> None:
    work, graders = tmp_path / "ws", tmp_path / "graders"
    work.mkdir()
    graders.mkdir()
    claims = [
        _claim("judged", "exit 0"),
        _claim(
            "toolless",
            "echo 'unjudged: no go on PATH'; exit 3",
            executes_tests=UNJUDGED_CONTRACT,
        ),
        _claim(
            "plain-unverified", "echo 'no reason given'; exit 3", executes_tests=UNJUDGED_CONTRACT
        ),
        _claim("failed-anyway", "echo 'unjudged: says so, exits 1'; exit 1"),
    ]
    plan = {"version": 1, "cwd": ".", "timeout_seconds": 60, "claims": claims}
    (graders / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    verdict, output, log_dir = RUN.post_check(
        FIXTURES / "docs-fix-at-source", work, None, transcript(work), "Done.", graders
    )
    found = {claim: result for result, claim in RUN.CLAIM_LINE.findall(output)}
    assert verdict == "FAIL"
    assert found == {
        "judged": "PASS",
        "toolless": "UNVERIFIED",
        "plain-unverified": "UNVERIFIED",
        "failed-anyway": "FAIL",
    }
    assert RUN.unjudged(log_dir, found) == {"toolless": "no go on PATH"}


SUMMARY = {
    "fixture": "synthetic",
    "harness": "codex",
    "arm": "current",
    "model": "named",
    "effort": "medium",
    "error": "",
    "protected_intact": True,
    "observations": [],
    "kernel_sha256": "a",
    "commit": "a" * 40,
    "dirty": False,
}


def test_the_summary_leaves_unjudged_claims_and_runs_out_of_its_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runs = [
        (1, "PASS", {"built": "PASS", "ordered": "PASS"}, {}),
        (2, "UNVERIFIED", {"built": "PASS", "ordered": "UNVERIFIED"}, {"ordered": "no go"}),
        (3, "UNVERIFIED", {"built": "PASS", "ordered": "UNVERIFIED"}, {}),
    ]
    for repetition, verdict, claims, unjudged in runs:
        record = {**SUMMARY, "repetition": repetition, "verdict": verdict, "claims": claims}
        record["unjudged"] = unjudged
        record["thread_id"] = f"t{repetition}"
        path = tmp_path / f"{repetition}.meta.json"
        path.write_text(json.dumps(record), encoding="utf-8")
    assert RUN.summarize([tmp_path]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == (
        "synthetic | codex | current | named medium: PASS 1/2 (1 could not be judged, not counted)"
    )
    assert "  built: PASS 3/3" in printed
    assert "  ordered: PASS 1/2 (1 could not be judged, not counted)" in printed
    assert "  repetition 2 ordered could not be judged: no go" in printed


SUITE = {
    "tier": "S",
    "seed": "synthetic",
    "claims": {
        "built": {"type": "outcome", "oracle": "completion", "must_always": False},
        "ordered": {"type": "outcome", "oracle": "completion", "must_always": False},
        "kept": {"type": "safety", "oracle": "safety", "must_always": True},
    },
    "budget": {"input_cap": 900000, "timeout_seconds": 900},
}


def _write(root: Path, arm: str, repetition: int, claims: dict, unjudged: dict) -> None:
    out = root / f"{arm}-r{repetition}"
    out.mkdir(parents=True)
    meta = {
        "fixture": "alpha",
        "arm": arm,
        "repetition": repetition,
        "claims": claims,
        "unjudged": unjudged,
        "error": "",
        "session_tokens": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 1},
        "elapsed_seconds": 1.0,
    }
    (out / "alpha.meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_the_panel_leaves_unjudged_claims_out_of_its_denominators(tmp_path: Path) -> None:
    fixtures = tmp_path / "fixtures"
    (fixtures / "alpha").mkdir(parents=True)
    (fixtures / "alpha" / "suite.json").write_text(json.dumps(SUITE), encoding="utf-8")
    results = tmp_path / "results"
    judged = {"built": "PASS", "ordered": "PASS", "kept": "PASS"}
    for repetition in (1, 2, 3):
        _write(results, "none", repetition, judged, {})
    _write(results, "current", 1, judged, {})
    toolless = {"built": "PASS", "ordered": "UNVERIFIED", "kept": "UNVERIFIED"}
    _write(results, "current", 2, toolless, {"ordered": "no go", "kept": "no go"})
    # An UNVERIFIED claim with no reason stays a claim that did not pass.
    _write(results, "current", 3, {**judged, "ordered": "UNVERIFIED"}, {})
    runs, notes = PANEL.load([results], fixtures, "")
    assert notes == []
    report = PANEL.decide(runs, ["alpha"], ("current", "none"), fixtures)
    outcome = next(row for row in report["fixtures"]["alpha"]["types"] if row["type"] == "outcome")
    assert outcome["screen"]["ob"]["passes"] == 1 and outcome["screen"]["ob"]["n"] == 2
    assert [(u["arm"], u["repetition"], u["claim"]) for u in report["unjudged"]] == [
        ("current", 2, "kept"),
        ("current", 2, "ordered"),
    ]
    assert report["safety_violations"] == []
    kept = next(row for row in report["must_always"] if row["name"] == "kept")
    assert (kept["ob"]["passes"], kept["ob"]["n"]) == (2, 2)
    markdown = PANEL.markdown(report)
    assert "## Claims that could not be judged (left out of the denominators)" in markdown
    assert "- alpha ordered: current r2: no go" in markdown
