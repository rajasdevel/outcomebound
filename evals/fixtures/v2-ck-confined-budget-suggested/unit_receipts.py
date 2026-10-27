"""Record direct unittest inputs and results; grading replay supplies no run evidence."""

from __future__ import annotations

import os
import unittest
from importlib import import_module
from unittest.mock import patch

checks = import_module("tools.checks")


def install():
    if os.environ.get("OUTCOMEBOUND_GRADER_DIR"):
        return
    before = checks.digest()
    run = unittest.TextTestRunner.run

    def recorded_run(self, test):
        checks.record("start", "direct-unit", before)
        result = run(self, test)
        status = 0 if result.wasSuccessful() and result.testsRun else 1
        checks.record("end", "direct-unit", before, status)
        return result

    patch.object(unittest.TextTestRunner, "run", recorded_run).start()
