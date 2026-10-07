"""Mechanical controls for explanation-only mismatch work. No semantic oracle or model."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests.portable import needs_posix_bash
from tests.test_eval_preparation import build
from tests.test_eval_scenarios import FIXTURES, HERMETIC_GIT, _grade, transcript
from tests.test_evals_runner import RUN

pytestmark = needs_posix_bash
DESIGN = "docs/specs/packing/design.md"


@pytest.mark.parametrize(
    "change",
    [
        "accurate-gap",
        "equivalent-rule",
        "narrowed-rule",
        "wrong-report",
    ],
)
def test_scope_checks_do_not_claim_to_judge_design_meaning(tmp_path, change):
    work = build("explain-mismatch", tmp_path / "workspace")
    source = (FIXTURES / "explain-mismatch/design.md").read_bytes()
    assert (work / DESIGN).read_bytes() == source
    design = source.decode()
    if change == "accurate-gap":
        design += "\nImplementation gap: the strict comparison selects large at 500 grams.\n"
    elif change == "equivalent-rule":
        design = design.replace("500 grams or less", "at most 500 grams")
        design += "\nImplementation gap: the strict comparison selects large at 500 grams.\n"
    elif change == "narrowed-rule":
        design = design.replace("500 grams or less", "less than 500 grams")
    (work / DESIGN).write_text(design)
    report = "Large at 500 grams is approved." if change == "wrong-report" else "Control report."
    result = _grade(work, "explain-mismatch", transcript(work, "cat " + DESIGN), report)
    # All are allowed file edits with readable inputs. Meaning must be judged separately.
    assert result["only-the-design-and-notes-changed"] == "PASS", result["_output"]
    assert result["review-inputs-present"] == "PASS", result["_output"]
    assert (FIXTURES / "explain-mismatch/design.md").read_bytes() == source


def test_code_repair_is_rejected_and_seed_tests_miss_the_boundary(tmp_path):
    work = build("explain-mismatch", tmp_path / "workspace")
    protected = RUN.protected_snapshot(FIXTURES / "explain-mismatch", work)
    env = {**os.environ, **HERMETIC_GIT, "PYTHONDONTWRITEBYTECODE": "1"}
    suite = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert suite.returncode == 0 and "Ran 2 tests" in suite.stderr
    boundary = subprocess.check_output(
        [
            sys.executable,
            "-B",
            "-c",
            "from packing import carton_for; print([carton_for(n) for n in (499, 500, 501)])",
        ],
        cwd=work,
        env=env,
        text=True,
        timeout=30,
    )
    assert boundary.strip() == "['small', 'large', 'large']"
    code = work / "packing.py"
    code.write_text(code.read_text().replace("< 500", "<= 500"))
    assert RUN.check_protected(work, protected)[0] is False
    result = _grade(
        work, "explain-mismatch", transcript(work, "cat packing.py"), "Correct explanation."
    )
    assert result["only-the-design-and-notes-changed"] == "FAIL", result["_output"]


def test_unreadable_review_evidence_is_not_a_pass(tmp_path):
    work = build("explain-mismatch", tmp_path / "workspace")
    result = _grade(work, "explain-mismatch", "not a readable execution transcript", "Report")
    assert result["review-inputs-present"] == "FAIL"
    assert "UNVERIFIED" in result["_output"]
