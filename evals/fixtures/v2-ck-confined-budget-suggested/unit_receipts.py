"""Record direct unit check inputs and results; grading replay supplies no run evidence."""

from __future__ import annotations

import os
import unittest
from importlib import import_module
from unittest.mock import patch

checks = import_module("tools.checks")
_installed = False
_pytest_before = ""
_pytest_ran = 0


def install():
    global _installed
    if _installed or os.environ.get("OUTCOMEBOUND_GRADER_DIR"):
        return
    _installed = True
    before = checks.digest()
    run = unittest.TextTestRunner.run

    def recorded_run(self, test):
        checks.record("start", "direct-unit", before)
        result = run(self, test)
        status = 0 if result.wasSuccessful() and result.testsRun else 1
        checks.record("end", "direct-unit", before, status)
        return result

    patch.object(unittest.TextTestRunner, "run", recorded_run).start()


def pytest_sessionstart(session):
    global _pytest_before, _pytest_ran
    if os.environ.get("OUTCOMEBOUND_GRADER_DIR"):
        return
    _pytest_before = checks.digest()
    _pytest_ran = 0
    checks.record("start", "direct-unit", _pytest_before)


def pytest_runtest_logreport(report):
    global _pytest_ran
    if report.when == "call" and not report.skipped:
        _pytest_ran += 1


def pytest_sessionfinish(session, exitstatus):
    if _pytest_before:
        status = int(exitstatus) if _pytest_ran else 1
        checks.record("end", "direct-unit", _pytest_before, status)
