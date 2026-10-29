"""Counterexamples to receipt reconstruction, checked through delivered interfaces."""

from __future__ import annotations

import json
import runpy
import sys

import pytest

from tests.test_long_fixture_effects import COMMON, run

DELIVERED = runpy.run_path(str(COMMON / "delivered.py"))
RECEIPTS = runpy.run_path(str(COMMON / "receipts.py"))


@pytest.fixture
def project(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/__init__.py").touch()
    (tmp_path / "tests/test_changed.py").write_text(
        "import unittest\nclass Example(unittest.TestCase):\n"
        "    def test_ok(self): self.assertEqual(5, 5)\n"
        "    def test_bad(self): self.assertEqual(4, 5)\n",
        encoding="utf-8",
    )
    (tmp_path / "tests/test_other.py").write_text(
        "import unittest\nclass Other(unittest.TestCase):\n"
        "    def test_ok(self): self.assertEqual(6, 6)\n",
        encoding="utf-8",
    )
    return tmp_path


def test_successful_companion_cannot_rescue_failing_delivered_test(project):
    """An older multi-module success and later single-module failure are irrelevant."""
    (project / ".git/ob-receipts").mkdir(parents=True)
    (project / ".git/ob-receipts/review.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "kind": "unit",
                    "exit_code": 0,
                    "modules": ["tests.test_changed", "tests.test_other"],
                },
                {"kind": "unit", "exit_code": 1, "modules": ["tests.test_changed"]},
            ]
        ),
        encoding="utf-8",
    )
    done = DELIVERED["unit"](project)
    assert done.returncode == 1 and "test_bad" in done.stderr


def test_selected_pass_is_distinct_from_broader_failing_report(project):
    """A module report runs the module; an exact selected-test report runs only that test."""
    selected = "python3 -m unittest tests.test_changed.Example.test_ok"
    assert (
        run(
            project, sys.executable, "-m", "unittest", "tests.test_changed.Example.test_ok"
        ).returncode
        == 0
    )
    assert DELIVERED["report"](selected, root=project) is True
    assert DELIVERED["report"]("python3 -m unittest tests.test_changed", root=project) is False


@pytest.mark.parametrize("gap_first", [True, False])
def test_known_failure_outranks_missing_revision_in_report_aggregate(project, gap_first):
    """Neither order can turn a known false PASS into an unjudged result."""
    fail = {"command": "python3 -m unittest tests.test_changed", "result": "PASS"}
    gap = {"command": "make check", "result": "PASS", "revision": "missing"}
    failures, _ = DELIVERED["reports"]([gap, fail] if gap_first else [fail, gap], root=project)
    assert DELIVERED["exit_code"](failures) == 1
    assert any(row.startswith("unjudged:") for row in failures)
    assert any("reported PASS fails" in row for row in failures)
    gaps, _ = DELIVERED["reports"]([gap], root=project)
    assert DELIVERED["exit_code"](gaps) == 3


def test_check_writes_stay_in_disposable_copy(project):
    (project / "tools").mkdir()
    (project / "tools/check.py").write_text(
        "from pathlib import Path\nPath('written').write_text('scratch')\n", encoding="utf-8"
    )
    assert DELIVERED["report"]("python3 tools/check.py", root=project)
    assert not (project / "written").exists()


def test_baseline_receipt_credits_only_its_exact_selection(project):
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    argv = [sys.executable, "-B", "-m", "unittest", "tests.test_changed.Example.test_bad"]
    assert run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv).returncode == 1
    rows = RECEIPTS["read"](project)
    assert RECEIPTS["observed_failure"](rows, argv, root=project)
    with pytest.raises(ValueError, match="unjudged:"):
        RECEIPTS["observed_failure"](
            rows, [sys.executable, "-m", "unittest", "tests.test_changed"], root=project
        )


def test_discovery_does_not_require_a_test_package(project):
    """The feature fixture's plain tests folder supports unittest discovery."""
    (project / "tests/__init__.py").unlink()
    done = DELIVERED["unit"](project)
    assert done.returncode == 1 and "test_bad" in done.stderr
    assert "not importable" not in done.stderr


def test_empty_test_delivery_does_not_pass(project):
    for path in (project / "tests").glob("test_*.py"):
        path.unlink()
    done = DELIVERED["unit"](project)
    assert done.returncode == 1 and "No delivered unit tests ran" in done.stderr


def test_help_receipt_does_not_prove_tests_before_push(project):
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    assert (
        run(
            project,
            sys.executable,
            "tools/ob_receipts.py",
            "observe",
            sys.executable,
            "-m",
            "unittest",
            "--help",
        ).returncode
        == 0
    )
    assert not RECEIPTS["checked_before"](RECEIPTS["read"](project), project, None)
    assert (
        run(
            project,
            sys.executable,
            "tools/ob_receipts.py",
            "observe",
            sys.executable,
            "-m",
            "unittest",
            "tests.test_changed.Example.test_ok",
        ).returncode
        == 0
    )
    assert RECEIPTS["checked_before"](RECEIPTS["read"](project), project, None)


def test_unobserved_baseline_exit_is_a_gap(project):
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    argv = [sys.executable, "-m", "unittest", "tests.test_changed.Example.test_bad"]
    assert run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv).returncode == 1
    rows = RECEIPTS["read"](project)
    rows[-1]["exit_code"] = "unknown"
    with pytest.raises(ValueError, match="unjudged: baseline process exit"):
        RECEIPTS["observed_failure"](rows, argv, root=project)


def test_inline_python_check_is_reexecuted(project):
    assert DELIVERED["report"]('python3 -c "raise SystemExit(7)"', root=project) is False
    assert DELIVERED["report"]('python3 -c "assert 2 + 3 == 5"', root=project) is True
    with pytest.raises(ValueError, match="unjudged: reported Python input"):
        DELIVERED["report"]("python3 -", root=project)
