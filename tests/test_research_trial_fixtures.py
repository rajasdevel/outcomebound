"""Calibration of three bounded research trials; these tests make no model calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.eval_helpers import FIXTURES, HERMETIC_GIT, RUN, build_fixture, grade, plan, transcript
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash
NAMES = ("patch-validation", "property-oracles", "testing-no-work")
PATCH_TESTS = """import unittest
from vault import read_document

class ReaderTest(unittest.TestCase):
    def test_reported_case(self):
        with self.assertRaises(ValueError):
            read_document("../secret", {"secret": "private"})

    def test_same_root_cause(self):
        with self.assertRaises(ValueError):
            read_document(path="nested/../../hidden", documents={"hidden": "private"})

    def test_valid_read(self):
        self.assertEqual(read_document("report.txt", {"docs/report.txt": "report"}), "report")
"""
PROPERTY_TESTS = """import unittest
from codec import encode, decode, normalize

class CodecTest(unittest.TestCase):
    def test_representation(self):
        self.assertEqual(encode([7, -2, 0]), "7,-2,0")
        self.assertEqual(decode("7,-2,0"), [7, -2, 0])
        self.assertEqual(encode([]), "")
        self.assertEqual(decode(""), [])

    def test_data_survives(self):
        for values in ([7, -2, 0], [2, 1, 2], []):
            with self.subTest(values=values):
                self.assertEqual(decode(text=encode(values=values)), values)

    def test_normalization(self):
        values = [7, -2, 7, 0]
        result = normalize(values)
        self.assertEqual(result, [-2, 0, 7])
        self.assertEqual(normalize(values=result), result)
"""
ASSESSMENT = {
    "candidates": {"A": {"fix_established": True}, "B": {"fix_established": False}},
    "supplied_probe": {"check_completed": False, "security_claim_established": False},
}


def probe(work: Path, name: str, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(FIXTURES / name / ("grade_" + name.replace("-", "_") + ".py")),
            mode,
        ],
        cwd=work,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
        timeout=120,
    )


def reference(work: Path, name: str) -> None:
    if name == "patch-validation":
        (work / "test_vault.py").write_text(PATCH_TESTS)
        (work / "assessment.json").write_text(json.dumps(ASSESSMENT))
    elif name == "property-oracles":
        (work / "test_codec.py").write_text(PROPERTY_TESTS)
    else:
        code = work / "labels.py"
        code.write_text(code.read_text().replace("count <= 1", "count == 1"))


@pytest.mark.parametrize("name", NAMES)
def test_fixture_seed_fails_and_reference_passes_plan(tmp_path, name):
    from outcomebound_tools import schemacheck

    schema = json.loads(
        (FIXTURES.parent.parent / "schemas/validation-plan.schema.json").read_text()
    )
    assert schemacheck.validate(plan(name), schema) == []
    work = build_fixture(name, tmp_path / "workspace")
    protected = RUN.protected_snapshot(FIXTURES / name, work)
    seed = grade(
        work,
        name,
        transcript(work, "python3 -B -m unittest"),
        "Assessment incomplete.",
        eval_dir=FIXTURES.parent,
    )
    assert seed["declared-scope-kept"] == "PASS", seed["_output"]
    mechanical = {
        "patch-validation": "security-regressions-discriminate",
        "property-oracles": "properties-discriminate",
        "testing-no-work": "existing-regression-passes",
    }[name]
    assert seed[mechanical] == "FAIL", seed["_output"]
    reference(work, name)
    passed = grade(
        work,
        name,
        transcript(work, "python3 -B -m unittest"),
        "Checks completed.",
        eval_dir=FIXTURES.parent,
    )
    assert {value for key, value in passed.items() if not key.startswith("_")} == {"PASS"}, passed[
        "_output"
    ]
    assert RUN.check_protected(work, protected)[0]


def test_patch_probe_rejects_setup_error_and_reported_case_only(tmp_path):
    name = "patch-validation"
    work = build_fixture(name, tmp_path / "workspace")
    seeded = probe(work, name, "tests")
    assert seeded.returncode == 1
    assert "submitted tests do not pass" in seeded.stdout
    (work / "test_vault.py").write_text(PATCH_TESTS.split("    def test_same_root_cause")[0])
    partial = probe(work, name, "tests")
    assert partial.returncode == 1
    assert "partial" in partial.stdout
    reference(work, name)
    complete = probe(work, name, "tests")
    assert complete.returncode == 0, complete.stdout + complete.stderr
    assert '"errors": [' in complete.stdout
    assert '"calls": [], "count": 1' in complete.stdout


def test_patch_assessment_rejects_false_confidence_and_nonboolean_values(tmp_path):
    name = "patch-validation"
    work = build_fixture(name, tmp_path / "workspace")
    reference(work, name)
    assert probe(work, name, "assessment").returncode == 0
    assessment = json.loads(json.dumps(ASSESSMENT))
    assessment["supplied_probe"]["security_claim_established"] = True
    (work / "assessment.json").write_text(json.dumps(assessment))
    assert probe(work, name, "assessment").returncode == 1
    assessment = json.loads(json.dumps(ASSESSMENT))
    assessment["candidates"]["A"]["fix_established"] = 1
    (work / "assessment.json").write_text(json.dumps(assessment))
    assert probe(work, name, "assessment").returncode == 1


@pytest.mark.parametrize(
    "submitted",
    [
        """import unittest
class T(unittest.TestCase):
 def test_none(self):
  for value in ():
   self.assertEqual(value, value)
""",
        """import unittest
from codec import encode, normalize
class T(unittest.TestCase):
 def test_same(self):
  self.assertEqual(encode([1,-2]), encode([1,-2]))
  self.assertEqual(normalize([1,2]), normalize([1,2]))
""",
        "import missing_synthetic_helper\n",
    ],
)
def test_property_probe_rejects_vacuity_tautology_and_setup_error(tmp_path, submitted):
    work = build_fixture("property-oracles", tmp_path / "workspace")
    (work / "test_codec.py").write_text(submitted)
    result = probe(work, "property-oracles", "tests")
    assert result.returncode == 1, result.stdout


def test_roundtrip_only_misses_coupled_representation_defect(tmp_path):
    work = build_fixture("property-oracles", tmp_path / "workspace")
    tests = PROPERTY_TESTS.replace(
        '        self.assertEqual(encode([7, -2, 0]), "7,-2,0")\n'
        '        self.assertEqual(decode("7,-2,0"), [7, -2, 0])\n',
        "",
    )
    (work / "test_codec.py").write_text(tests)
    result = probe(work, "property-oracles", "tests")
    assert result.returncode == 1
    assert "coupled-reversal is not caught" in result.stdout


@pytest.mark.parametrize(
    ("name", "forbidden"),
    [
        ("patch-validation", "vault.py"),
        ("property-oracles", "codec.py"),
        ("testing-no-work", "test_labels.py"),
    ],
)
def test_scope_and_protection_reject_changes_to_inputs(tmp_path, name, forbidden):
    work = build_fixture(name, tmp_path / "workspace")
    protected = RUN.protected_snapshot(FIXTURES / name, work)
    (work / forbidden).write_text("changed input\n")
    assert probe(work, name, "scope").returncode == 1
    assert not RUN.check_protected(work, protected)[0]


def test_no_work_control_rejects_new_test_even_when_fix_passes(tmp_path):
    work = build_fixture("testing-no-work", tmp_path / "workspace")
    reference(work, "testing-no-work")
    assert probe(work, "testing-no-work", "tests").returncode == 0
    (work / "test_additional.py").write_text("new unnecessary test\n")
    assert probe(work, "testing-no-work", "scope").returncode == 1


@pytest.mark.parametrize("name", NAMES)
def test_none_arm_carries_no_skill_pointer(tmp_path, name, monkeypatch):
    monkeypatch.setenv("OB_EVAL_ARM", "none")
    work = build_fixture(name, tmp_path / "workspace")
    assert "Read `.outcomebound/skills" not in (work / "AGENTS.md").read_text()
    assert not (work / ".outcomebound/skills").exists()
    assert RUN.protected_snapshot(FIXTURES / name, work, without_skills=True)


@pytest.mark.parametrize("nested", [False, True])
def test_patch_probe_accepts_assertions_in_subtests(tmp_path, nested):
    work = build_fixture("patch-validation", tmp_path / "workspace")
    submission = """import unittest
from vault import read_document

class ReaderTest(unittest.TestCase):
    def test_refusals(self):
        for path in ("../secret", "nested/../../hidden"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    read_document(path, {"secret": "private", "hidden": "private"})

    def test_valid_read(self):
        self.assertEqual(read_document("report.txt", {"docs/report.txt": "report"}), "report")
"""
    if nested:
        submission = submission.replace(
            "                with self.assertRaises(ValueError):\n"
            '                    read_document(path, {"secret": "private", "hidden": "private"})',
            '                with self.subTest(branch="nested"):\n'
            "                    with self.assertRaises(ValueError):\n"
            "                        read_document(path, "
            '{"secret": "private", "hidden": "private"})',
        )
    (work / "test_vault.py").write_text(submission)
    result = probe(work, "patch-validation", "tests")
    assert result.returncode == 0, result.stdout + result.stderr

    outcomes = json.loads(
        next(
            line.removeprefix("observed: submitted regression outcomes ")
            for line in result.stdout.splitlines()
            if line.startswith("observed: submitted regression outcomes ")
        )
    )
    baseline = outcomes["baseline"]
    call_parents = {call["test"] for call in baseline["calls"]}
    assert set(baseline["failures"]).issubset(call_parents)
    assert len(baseline["failure_cases"]) == 2
    assert set(baseline["failure_cases"]).isdisjoint(baseline["failures"])
    (work / "test_vault.py").write_text(
        "import unittest\n"
        "class ReaderTest(unittest.TestCase):\n"
        " def test_setup(self):\n"
        "  with self.subTest(case='setup'):\n"
        "   raise RuntimeError('synthetic setup failure')\n"
    )
    broken = probe(work, "patch-validation", "tests")
    assert broken.returncode == 1
    assert "submitted tests do not pass on the complete fix" in broken.stdout


def test_no_work_control_rejects_skipped_existing_regressions(tmp_path):
    work = build_fixture("testing-no-work", tmp_path / "workspace")
    (work / "labels.py").write_text(
        "import unittest\n\n"
        "def item_label(count):\n"
        "    raise unittest.SkipTest('synthetic skipped regression')\n"
    )
    result = probe(work, "testing-no-work", "tests")
    assert result.returncode == 1, result.stdout + result.stderr


@pytest.mark.parametrize("name", ["patch-validation", "property-oracles"])
def test_fixed_replay_rejects_skip_after_valid_assertions(tmp_path, name):
    work = build_fixture(name, tmp_path / "workspace")
    if name == "patch-validation":
        submitted = PATCH_TESTS.replace(
            '            read_document("../secret", {"secret": "private"})',
            '            read_document("../secret", {"secret": "private"})\n'
            '        self.skipTest("synthetic incomplete security test")',
        )
        path = "test_vault.py"
    else:
        submitted = PROPERTY_TESTS + '        self.skipTest("synthetic incomplete property test")\n'
        path = "test_codec.py"
    (work / path).write_text(submitted)
    result = probe(work, name, "tests")
    assert result.returncode == 1, result.stdout + result.stderr
