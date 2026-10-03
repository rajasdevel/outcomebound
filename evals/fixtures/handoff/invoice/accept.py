"""Hidden acceptance for ticket #8: `timelog report --json` feeds `invoice.py`.

Run from the workspace by `grade.py accept invoice`. Every row is a decision the ticket or
`docs/report-json.md` states; none depends on how the change is built.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


def _beside(name: str) -> ModuleType:
    """A grader module beside this base's directory, loaded by path."""

    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent.parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside the hand-off bases")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


accepting = _beside("accepting")
Log = accepting.Log
command = accepting.command
rows = accepting.rows

LOG = (
    "2026-08-31\tacme\t60\t\n"
    "2026-09-01\tacme\t90\tkickoff\n"
    "2026-09-15\tbeta\t45\t\n"
    "2026-09-30\tacme\t30\t\n"
    "2026-10-01\tbeta\t15\t\n"
)
SEPTEMBER = ("--from", "2026-09-01", "--to", "2026-09-30")


class InvoiceAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.log = Log(LOG)
        self.addCleanup(self.log.close)

    def report(self, *argv: str) -> Any:
        done = self.log.run("report", "--json", *argv)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_range_prints_the_shape(self) -> None:
        self.assertEqual(
            self.report(*SEPTEMBER),
            {
                "from": "2026-09-01",
                "to": "2026-09-30",
                "projects": [
                    {"project": "acme", "minutes": 120},
                    {"project": "beta", "minutes": 45},
                ],
                "total_minutes": 165,
            },
        )

    def test_a_day_not_given_is_null(self) -> None:
        self.assertEqual(
            self.report(),
            {
                "from": None,
                "to": None,
                "projects": [
                    {"project": "acme", "minutes": 180},
                    {"project": "beta", "minutes": 60},
                ],
                "total_minutes": 240,
            },
        )
        self.assertEqual(self.report("--to", "2026-08-31")["from"], None)

    def test_no_entries_is_the_empty_shape(self) -> None:
        self.assertEqual(
            self.report("--from", "2027-01-01"),
            {"from": "2027-01-01", "to": None, "projects": [], "total_minutes": 0},
        )

    def test_the_month_s_invoice_is_one_pipe(self) -> None:
        done = self.log.run("report", "--json", *SEPTEMBER)
        billed = command("invoice.py", "--rate", "90", stdin=done.stdout)
        self.assertEqual(billed.returncode, 0, billed.stderr)
        self.assertEqual(
            rows(billed.stdout),
            [
                ["period", "2026-09-01", "to", "2026-09-30"],
                ["acme", "2:00", "180.00"],
                ["beta", "0:45", "67.50"],
                ["total", "2:45", "247.50"],
            ],
        )

    def test_an_empty_report_is_invoiced_as_nothing(self) -> None:
        done = self.log.run("report", "--json", "--from", "2027-01-01")
        billed = command("invoice.py", "--rate", "90", stdin=done.stdout)
        self.assertEqual(billed.returncode, 0, billed.stderr)
        self.assertEqual(rows(billed.stdout)[-1], ["nothing", "to", "bill"])

    def test_the_text_report_is_unchanged(self) -> None:
        done = self.log.run("report", *SEPTEMBER)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(rows(done.stdout), [["acme", "2:00"], ["beta", "0:45"], ["total", "2:45"]])


if __name__ == "__main__":
    unittest.main()
