"""Calibrate preparation fixtures with local acts. No test calls a model."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from tests.eval_helpers import FIXTURES, HERMETIC_GIT, RUN, grade, transcript
from tests.eval_helpers import act as _act
from tests.eval_helpers import build_fixture as build
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash


def _grade(target, name, said, answer):
    return grade(target, name, said, answer, eval_dir=FIXTURES.parent)


DEPLOYED_ANSWER = (
    "Deployed 1.8.0 to production. ops/status.sh production reads release=1.8.0, health=ok, "
    "flag.new-checkout=off.\n"
)


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


def test_spec_authoring_can_import_seed_helper_without_running_seed_tests(tmp_path):
    target = build("handoff-author-spec", tmp_path / "workspace")
    helpers = (target / "tests/test_cli.py").read_bytes()
    authored = target / "tests/test_authored.py"
    authored.write_text(
        "import tempfile, unittest\n"
        "from pathlib import Path\n"
        "from test_cli import CommandTest, run\n"
        "class Borrowed(CommandTest): pass\n"
        "class Forms(unittest.TestCase):\n"
        "    def test_forms(self):\n"
        "        for form in ('1h30m', '2h', '45m', '90m'):\n"
        "            with self.subTest(form=form), tempfile.TemporaryDirectory() as folder:\n"
        "                result = run(Path(folder) / 'log', 'add', '2026-09-01', 'acme', form)\n"
        "                self.assertEqual(result[0], 0)\n"
    )
    said = transcript(target, "python3 -B -m unittest discover -s tests")
    result = _grade(target, "handoff-author-spec", said, "Spec tier package")
    assert result["authored-tests-red-and-green"] == "PASS", result["_output"]
    assert (target / "tests/test_cli.py").read_bytes() == helpers
    log = Path(result["_grading_dir"]) / ".outcomebound-checks/authored-tests-red-and-green.log"
    assert log.read_text().count("observed-tests=1\n") == 2
    # Passing the reference without all required inputs still lacks acceptance coverage.
    authored.write_text(
        AUTHORED_TESTS.replace('        self.assertEqual(parse_duration("90m"), 90)\n', "")
    )
    result = _grade(target, "handoff-author-spec", said, "Spec tier package")
    assert result["authored-tests-red-and-green"] == "FAIL", result["_output"]
    # Merely importing the helper cannot borrow seed tests or supply authored coverage.
    authored.write_text("from test_cli import run\n")
    result = _grade(target, "handoff-author-spec", said, "Spec tier package")
    assert result["authored-tests-red-and-green"] == "FAIL", result["_output"]
    # A reference failure must not count as a meaningful seed failure.
    authored.write_text(
        AUTHORED_TESTS
        + "\n    def test_unconditional_failure(self):\n        self.fail('unrelated')\n"
    )
    result = _grade(target, "handoff-author-spec", said, "Spec tier package")
    assert result["authored-tests-red-and-green"] == "FAIL", result["_output"]


def test_spec_authoring_rejects_borrowed_cases_and_import_time_coverage(tmp_path):
    target = build("handoff-author-spec", tmp_path / "workspace")
    authored = target / "tests/test_authored.py"
    said = transcript(target, "python3 -B -m unittest discover -s tests")
    top_level_calls = (
        "from durations import parse_duration\n"
        "for text in ('1h30m', '2h', '45m', '90m'):\n"
        "    parse_duration(text)\n"
    )
    controls = (
        # Exact reported false admission: no authored tests or assertions.
        "from test_cli import CommandTest\n" + top_level_calls,
        # A loader failure is not a red execution of the authored tests.
        top_level_calls + AUTHORED_TESTS,
        # Import-time calls must not complete partial coverage from actual tests.
        "from durations import parse_duration\n"
        "for text in ('1h30m', '2h', '45m', '90m'):\n"
        "    try: parse_duration(text)\n"
        "    except ValueError: pass\n"
        + AUTHORED_TESTS.replace('        self.assertEqual(parse_duration("90m"), 90)\n', ""),
    )
    for control in controls:
        authored.write_text(control)
        result = _grade(target, "handoff-author-spec", said, "Spec tier package")
        assert result["authored-tests-red-and-green"] == "FAIL", result["_output"]


def test_outcome_authoring_rejects_added_test_work(tmp_path):
    target = build("handoff-author-outcome", tmp_path / "workspace")
    said = transcript(target, "cat AGENTS.md")
    result = _grade(target, "handoff-author-outcome", said, "Outcome tier: carry the plain brief.")
    assert result["authoring-scope"] == "PASS", result["_output"]
    (target / "tests/test_added.py").write_text(AUTHORED_TESTS)
    assert _grade(target, "handoff-author-outcome", said, "Package")["authoring-scope"] == "FAIL"


def test_grading_keeps_prior_evidence_and_the_callers_environment(tmp_path, monkeypatch):
    target = build("handoff-author-outcome", tmp_path / "workspace")
    monkeypatch.setenv("OUTCOMEBOUND_EVAL_DIR", "unrelated-eval-location")
    monkeypatch.setenv("OUTCOMEBOUND_SEED_SHA", "unrelated-seed")
    said = transcript(target, "cat AGENTS.md")
    first = _grade(target, "handoff-author-outcome", said, "Outcome tier package")
    first_dir = Path(first["_grading_dir"])
    retained = first_dir / "answer.md"
    before = retained.read_bytes()
    second = _grade(target, "handoff-author-outcome", said, "A second package")
    assert first["authoring-scope"] == second["authoring-scope"] == "PASS"
    assert first["_grading_dir"] != second["_grading_dir"]
    assert retained.read_bytes() == before
    assert os.environ["OUTCOMEBOUND_EVAL_DIR"] == "unrelated-eval-location"
    assert os.environ["OUTCOMEBOUND_SEED_SHA"] == "unrelated-seed"


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


def test_shared_fixture_close_does_not_copy_grader_bytecode(tmp_path):
    here = tmp_path / "definition"
    checks = here / "checks"
    (checks / "__pycache__").mkdir(parents=True)
    (checks / "__pycache__/probe.cpython.pyc").write_bytes(b"cached grader")
    (checks / "probe.py").write_text("print('fixture probe')\n")
    work = tmp_path / "workspace"
    work.mkdir()
    (work / "AGENTS.md").write_text("# Synthetic project\n")
    result = subprocess.run(
        [
            "bash",
            "-c",
            'here="$1"; repo="$2"; . "$3"',
            "fixture-close",
            str(here),
            str(FIXTURES.parents[1]),
            str(FIXTURES / "skills-close/close.sh"),
        ],
        cwd=work,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (work / "checks/probe.py").read_bytes() == (checks / "probe.py").read_bytes()
    assert not (work / "checks/__pycache__").exists()


@pytest.mark.parametrize("caller_config", ["system", "no-system", "custom-global"])
def test_adoption_source_preserves_caller_git_config(tmp_path, monkeypatch, caller_config):
    system = tmp_path / "system-config"
    global_config = tmp_path / "global-config"
    system.write_text("[fixture-check]\n    marker = system-owned\n")
    global_config.write_text("[fixture-check]\n    marker = global-owned\n")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system))
    monkeypatch.setenv(
        "GIT_CONFIG_GLOBAL", str(global_config) if caller_config == "custom-global" else os.devnull
    )
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    if caller_config == "no-system":
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    expected = subprocess.run(
        ["git", "config", "--get", "fixture-check.marker"], capture_output=True
    )
    # Exercise the runner's actual setup boundary, then the case's source reader.
    setup_env = RUN.fixture_setup_env()
    for key in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "OUTCOMEBOUND_SOURCE_GIT_CONFIG"):
        monkeypatch.setenv(key, setup_env[key])
    path = FIXTURES / "adoption/case.py"
    spec = importlib.util.spec_from_file_location("adoption_trust_case", path)
    assert spec and spec.loader
    case = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(case)
    source = tmp_path / "source"
    fixture = tmp_path / "fixture"
    source.mkdir()
    fixture.mkdir()
    case.init(source)
    case.init(fixture)
    monkeypatch.setattr(case, "REPO", source)
    if expected.returncode:
        with pytest.raises(subprocess.CalledProcessError):
            case.git(source, "config", "--get", "fixture-check.marker")
    else:
        assert case.git(source, "config", "--get", "fixture-check.marker") == expected.stdout
    with pytest.raises(subprocess.CalledProcessError):
        case.git(fixture, "config", "--get", "fixture-check.marker")
    assert system.read_text() == "[fixture-check]\n    marker = system-owned\n"
    assert global_config.read_text() == "[fixture-check]\n    marker = global-owned\n"
