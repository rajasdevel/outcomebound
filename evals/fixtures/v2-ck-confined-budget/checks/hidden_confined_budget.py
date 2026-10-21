"""Hidden tests of v2-ck-confined-budget, run by the grader against the workspace's package."""

import importlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The workspace's own package: it exists only in the built workspace, so it is imported
# by name when the tests run.
_display = importlib.import_module("ledger.display")
format_amount = _display.format_amount


class FormatAmountHidden(unittest.TestCase):
    def test_amounts_of_each_sign(self):
        cases = {
            0: "0.00",
            5: "0.05",
            1234: "12.34",
            123456: "1234.56",
            -5: "-0.05",
            -50: "-0.50",
            -100: "-1.00",
            -1250: "-12.50",
            -123456: "-1234.56",
        }
        for cents, want in cases.items():
            with self.subTest(cents=cents):
                self.assertEqual(format_amount(cents), want)

    def test_balance_on_the_command_line(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "data"
            shutil.copytree("data", data)
            done = subprocess.run(
                [sys.executable, "-B", "-m", "ledger", "--data", str(data), "balance", "acc-003"],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
            )
        self.assertEqual(done.stdout.strip(), "-12.50", done.stderr)


if __name__ == "__main__":
    unittest.main()
