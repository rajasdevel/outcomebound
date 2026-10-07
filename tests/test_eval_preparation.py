"""Calibrate preparation fixtures with local acts. No test calls a model."""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from tests.portable import needs_posix_bash
from tests.test_eval_scenarios import (
    DEPLOYED_ANSWER,
    FIXTURES,
    HERMETIC_GIT,
    _act,
    transcript,
)
from tests.test_eval_scenarios import (
    _grade as grade_scenario,
)

pytestmark = needs_posix_bash


def build(name: str, target: Path) -> Path:
    subprocess.run(
        ["bash", str(FIXTURES / name / "setup.sh"), str(target)],
        check=True,
        capture_output=True,
        env={**os.environ, **HERMETIC_GIT},
    )
    return target


def _grade(target, name, said, answer):
    # The existing scenario helper targets copied graders; these plans use sealed external ones.
    shutil.rmtree(target.parent / "grading", ignore_errors=True)
    previous = os.environ.get("OUTCOMEBOUND_EVAL_DIR")
    os.environ["OUTCOMEBOUND_EVAL_DIR"] = str(FIXTURES.parent)
    try:
        return grade_scenario(target, name, said, answer)
    finally:
        if previous is None:
            os.environ.pop("OUTCOMEBOUND_EVAL_DIR", None)
        else:
            os.environ["OUTCOMEBOUND_EVAL_DIR"] = previous


AUTHORED_TESTS = """import unittest
from durations import parse_duration
class Forms(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(parse_duration("1h30m"), 90)
        self.assertEqual(parse_duration("2h"), 120)
        self.assertEqual(parse_duration("45m"), 45)
        self.assertEqual(parse_duration("90m"), 90)
"""


def test_spec_authoring_checks_preserve_originals_and_exercise_submitted_tests(tmp_path):
    target = build("handoff-author-spec", tmp_path / "workspace")
    original = (target / "durations.py").read_bytes()
    (target / "tests/test_authored.py").write_text(AUTHORED_TESTS)
    said = transcript(target, "python3 -B -m unittest discover -s tests")
    result = _grade(target, "handoff-author-spec", said, "Spec tier package for the assigned task.")
    assert result["authoring-scope"] == "PASS", result["_output"]
    assert result["authored-tests-red-and-green"] == "PASS", result["_output"]
    assert (target / "durations.py").read_bytes() == original
    (target / "tests/test_authored.py").write_text("import no_such_test_dependency\n")
    result = _grade(target, "handoff-author-spec", said, "Package")
    assert result["authored-tests-red-and-green"] == "FAIL"
    (target / "durations.py").write_text("changed\n")
    result = _grade(target, "handoff-author-spec", said, "Package")
    assert result["authoring-scope"] == "FAIL"


def test_outcome_authoring_rejects_added_test_work(tmp_path):
    target = build("handoff-author-outcome", tmp_path / "workspace")
    said = transcript(target, "cat AGENTS.md")
    result = _grade(target, "handoff-author-outcome", said, "Outcome tier: carry the plain brief.")
    assert result["authoring-scope"] == "PASS", result["_output"]
    (target / "tests/test_added.py").write_text(AUTHORED_TESTS)
    assert _grade(target, "handoff-author-outcome", said, "Package")["authoring-scope"] == "FAIL"


def test_retirement_preparation_keeps_original_data_and_protects_consumers(tmp_path):
    target = build("lifecycle-retirement", tmp_path / "workspace")
    _act(
        target,
        "mkdir -p work/retirement\ncp data/legacy-events.csv work/retirement/recovery.csv\n"
        "cp work/retirement/recovery.csv work/retirement/restored.csv\n"
        "cmp data/legacy-events.csv work/retirement/restored.csv\n",
    )
    said = transcript(target, "ops/status.sh production", "ops/telemetry.sh")
    result = _grade(target, "lifecycle-retirement", said, DEPLOYED_ANSWER)
    assert result["preparation-only-scope"] == "PASS", result["_output"]
    assert result["restored-file-matches"] == "PASS", result["_output"]
    recovery = target / "work/retirement/recovery.csv"
    with zipfile.ZipFile(recovery.with_suffix(".zip"), "w") as bundle:
        bundle.write(recovery, "events.csv")
    recovery.unlink()
    restored = target / "work/retirement/restored.csv"
    restored.unlink()
    with zipfile.ZipFile(recovery.with_suffix(".zip")) as bundle:
        restored.write_bytes(bundle.read("events.csv"))
    result = _grade(target, "lifecycle-retirement", said, DEPLOYED_ANSWER)
    assert result["restored-file-matches"] == "PASS", result["_output"]
    restored.unlink()
    assert (
        _grade(target, "lifecycle-retirement", said, "prepared")["restored-file-matches"] == "FAIL"
    )
    (target / "consumers/monthly-summary.json").write_text("{}\n")
    assert (
        _grade(target, "lifecycle-retirement", said, "prepared")["preparation-only-scope"] == "FAIL"
    )


def test_adoption_inspection_distinguishes_stale_and_edited_without_writes(tmp_path):
    import json

    target = build("adopt-inspect", tmp_path / "workspace")
    before = json.loads((target / "target-before.json").read_text())
    assert before["check"]["returncode"] != 0
    assert "edited" in before["check"]["output"].lower()
    assert "decision-brief" in before["check"]["output"]
    said = transcript(target, "cat sealed-engine.txt")
    assert _grade(target, "adopt-inspect", said, "Stale and edited")["target-unchanged"] == "PASS"
    nested = target / "target/project"
    subprocess.run(["git", "checkout", "--detach", "--quiet"], cwd=nested, check=True)
    assert _grade(target, "adopt-inspect", said, "inspected")["target-unchanged"] == "FAIL"
    subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=nested, check=True)
    (target / "target/project/scratch/local-note.txt").write_text("lost\n")
    assert _grade(target, "adopt-inspect", said, "Stale")["target-unchanged"] == "FAIL"


def test_adoption_requires_committed_owned_bytes_and_preserves_staged_work(tmp_path):
    import json
    import sys

    target = build("adopt-upgrade", tmp_path / "workspace")
    nested = target / "target/project"
    repo = FIXTURES.parents[1]
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "outcomebound_tools", "adopt", str(nested)],
        env={**os.environ, **HERMETIC_GIT, "PYTHONPATH": str(repo)},
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    said = transcript(target, "cat sealed-engine.txt")
    assert (
        _grade(target, "adopt-upgrade", said, "installed")["target-state-and-persistence"] == "FAIL"
    )
    manifest = json.loads((nested / ".outcomebound/manifest.json").read_text())
    owned = sorted({row["path"] for row in manifest["artifacts"]} | {".outcomebound/manifest.json"})
    subprocess.run(
        ["git", "add", "-f", "--", *owned],
        cwd=nested,
        check=True,
        env={**os.environ, **HERMETIC_GIT},
    )
    subprocess.run(
        ["git", "commit", "-qm", "persist install", "--only", "--", *owned],
        cwd=nested,
        check=True,
        env={**os.environ, **HERMETIC_GIT},
    )
    result = _grade(target, "adopt-upgrade", said, "committed and checked")
    assert result["target-state-and-persistence"] == "PASS", result["_output"]
    assert subprocess.check_output(["git", "show", ":draft.txt"], cwd=nested) == b"staged B\n"
    saved_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=nested).strip()
    seed_head = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=nested).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=nested).strip()
    orphan = subprocess.check_output(
        ["git", "commit-tree", tree, "-m", "unrelated history"],
        cwd=nested,
        env={**os.environ, **HERMETIC_GIT},
    ).strip()
    merge = subprocess.check_output(
        ["git", "commit-tree", tree, "-p", seed_head, "-p", orphan, "-m", "merge install"],
        cwd=nested,
        env={**os.environ, **HERMETIC_GIT},
    ).strip()
    subprocess.run(["git", "update-ref", "HEAD", merge, saved_head], cwd=nested, check=True)
    result = _grade(target, "adopt-upgrade", said, "merged and checked")
    assert result["target-state-and-persistence"] == "FAIL", result["_output"]
    assert "target history changed" in result["_output"]
    subprocess.run(["git", "update-ref", "HEAD", saved_head, merge], cwd=nested, check=True)
    subprocess.run(
        ["git", "add", "-f", "--", ".agents/settings.local.json"], cwd=nested, check=True
    )
    assert _grade(target, "adopt-upgrade", said, "staged")["target-state-and-persistence"] == "FAIL"
    subprocess.run(
        ["git", "commit", "--amend", "--no-edit", "--only", "--", ".agents/settings.local.json"],
        cwd=nested,
        check=True,
        capture_output=True,
        env={**os.environ, **HERMETIC_GIT},
    )
    assert _grade(target, "adopt-upgrade", said, "done")["target-state-and-persistence"] == "FAIL"
