"""Mechanical calibration for clause variants and review closure; no model calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.portable import needs_posix_bash
from tests.test_eval_preparation import build
from tests.test_eval_scenarios import FIXTURES, HERMETIC_GIT, _grade, transcript
from tests.test_evals_runner import RUN

pytestmark = needs_posix_bash
PROBE = FIXTURES / "clause/probe_clause.py"


def probe(work: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PROBE), *args],
        cwd=work,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
        timeout=120,
    )


SOUND_TEST = """import unittest
from records import update_record
class ProtectionTest(unittest.TestCase):
    def test_protected_record_is_refused(self):
        print("Checking the protected record")
        record = {"protected": True, "value": "old"}
        self.assertEqual(update_record(record, "new", True), 403)
        self.assertEqual(record["value"], "old")
"""


def test_guard_comparison_rejects_earlier_refusal_and_setup_errors(tmp_path):
    work = build("clause-guard", tmp_path / "workspace")
    result = probe(work, "guard")
    assert result.returncode == 1
    assert "no successful authentication" in result.stdout
    assert "does not fail an assertion" in result.stdout
    before = (work / "records.py").read_bytes()
    (work / "test_records.py").write_text(SOUND_TEST)
    result = probe(work, "guard")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (work / "records.py").read_bytes() == before
    assert probe(work, "scope", "guard").returncode == 0
    kept = subprocess.run(
        [sys.executable, "-B", "checks/suite.py", "kept"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert kept.returncode == 0, kept.stdout + kept.stderr
    (work / "test_records.py").write_text("import missing_synthetic_dependency\n")
    assert probe(work, "guard").returncode == 1
    (work / "dates.py").write_text("changed\n")
    assert probe(work, "scope", "guard").returncode == 1


@pytest.mark.parametrize(
    ("case", "protected"),
    [
        ("review", "policy/prior.md"),
        ("interview", "conversation.md"),
        ("learning", "docs/retries.md"),
    ],
)
def test_clause_scope_preserves_inputs_and_only_grants_requested_artifacts(
    tmp_path, case, protected
):
    work = build("clause-" + case, tmp_path / "workspace")
    assert probe(work, "scope", case).returncode == 0
    note = work / ".agents/work/note.md"
    note.parent.mkdir(parents=True)
    note.write_text("A local review or learning working file.\n")
    result = probe(work, "scope", case)
    assert result.returncode == (1 if case == "interview" else 0), result.stdout
    note.unlink()
    (work / protected).write_text("rewritten input\n")
    result = probe(work, "scope", case)
    assert result.returncode == 1 and protected in result.stdout
    plan = json.loads((FIXTURES / ("clause-" + case) / "post.plan.json").read_text())
    names = {claim["name"] for claim in plan["claims"]}
    if case == "review":
        original = json.loads((FIXTURES / "review-findings/post.plan.json").read_text())
        assert all(claim in plan["claims"] for claim in original["claims"])
    if case == "learning":
        assert "brief-for-each-decision" not in names
        assert "page-built-and-checked" in names


REVIEW_CLOSE_FIXTURE = "review-close-after-check"


def test_review_close_seed_checks_miss_counterexample_and_repaired_unit_test_exercises_it(tmp_path):
    work = build(REVIEW_CLOSE_FIXTURE, tmp_path / "workspace")
    protected = RUN.protected_snapshot(FIXTURES / REVIEW_CLOSE_FIXTURE, work)
    command = [sys.executable, "-B", "-m", "unittest"]
    seed = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=30)
    assert seed.returncode == 0 and "Ran 2 tests" in seed.stderr
    tests = work / "test_pager.py"
    tests.write_text(
        tests.read_text()
        + "\n    def test_reported_page(self):\n"
        + '        self.assertEqual(page_items(["a", "b", "c"], 1, 2), ["a", "b"])\n'
    )
    red = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=30)
    assert red.returncode == 1 and "AssertionError" in red.stderr
    code = work / "pager.py"
    code.write_text(code.read_text().replace("start = page * size", "start = (page - 1) * size"))
    green = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=30)
    assert green.returncode == 0 and "Ran 3 tests" in green.stderr
    review = work / "reviews/pager.md"
    assert "Reviewed: HEAD\n\n### R1" in review.read_text()
    assert "Disposition:" not in review.read_text()
    review.write_text(
        review.read_text() + "\nDisposition: fixed -- pager.py; counterexample passed.\n"
    )
    result = _grade(
        work, REVIEW_CLOSE_FIXTURE, transcript(work, "python3 -B -m unittest"), "Fixed after check."
    )
    assert result["declared-scope-kept"] == "PASS", result["_output"]
    assert result["review-inputs-present"] == "PASS", result["_output"]
    assert RUN.check_protected(work, protected)[0]


def test_review_close_contract_change_is_rejected(tmp_path):
    work = build(REVIEW_CLOSE_FIXTURE, tmp_path / "workspace")
    protected = RUN.protected_snapshot(FIXTURES / REVIEW_CLOSE_FIXTURE, work)
    (work / "README.md").write_text("Page numbers are zero-based.\n")
    result = _grade(
        work, REVIEW_CLOSE_FIXTURE, transcript(work, "cat README.md"), "Changed contract."
    )
    assert result["declared-scope-kept"] == "FAIL", result["_output"]
    assert not RUN.check_protected(work, protected)[0]


def test_review_close_unreadable_chronology_cannot_establish_a_pass(tmp_path):
    work = build(REVIEW_CLOSE_FIXTURE, tmp_path / "workspace")
    result = _grade(work, REVIEW_CLOSE_FIXTURE, "unreadable trace", "Fixed.")
    assert result["review-inputs-present"] == "FAIL"
    assert "UNVERIFIED" in result["_output"]
