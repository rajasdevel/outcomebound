"""Hidden acceptance for ticket #7: `timelog add` reads hours and minutes.

Run from the workspace by `grade.py accept duration`. Every row is a decision the ticket
states; none depends on how the change is built.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


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

READ = {
    "90": 90,
    "1h30m": 90,
    "2h": 120,
    "10h": 600,
    "45m": 45,
    "90m": 90,
    " 1h30m ": 90,
    "0h30m": 30,
    "1h0m": 60,
    "1h59m": 119,
}
REFUSED = (
    "1h60m",
    "1h75m",
    "1h 30m",
    "1H30M",
    "1h30",
    "30m1h",
    "1hm",
    "h",
    "m",
    "",
    "0h",
    "0m",
    "0h0m",
    "0",
    "1.5h",
    "-1h",
)


class DurationAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.parse = accepting.workspace_module("durations").parse_duration

    def test_each_form_the_ticket_reads(self) -> None:
        for text, minutes in READ.items():
            with self.subTest(text=text):
                self.assertEqual(self.parse(text), minutes)

    def test_each_form_the_ticket_refuses(self) -> None:
        for text in REFUSED:
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "invalid duration"):
                self.parse(text)

    def test_add_records_hours_and_minutes_as_minutes(self) -> None:
        log = Log()
        self.addCleanup(log.close)
        done = log.run("add", "2026-10-01", "acme", "1h30m", "review")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(log.text(), "2026-10-01\tacme\t90\treview\n")

    def test_add_refuses_a_duration_and_writes_nothing(self) -> None:
        log = Log()
        self.addCleanup(log.close)
        done = log.run("add", "2026-10-01", "acme", "1h75m")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("timelog: invalid duration: '1h75m'", done.stderr)
        self.assertEqual(log.text(), "")


if __name__ == "__main__":
    unittest.main()
