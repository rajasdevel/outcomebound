"""Hidden acceptance for ticket #9: tags on entries, and the report of one tag.

Run from the workspace by `grade.py accept tags`. Every row is a decision the ticket states;
none depends on how the change is built.
"""

from __future__ import annotations

import importlib.util
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
rows = accepting.rows

# A log written before tags: four fields a line.
BEFORE = "2026-09-01\tacme\t30\t\n2026-09-01\tbeta\t15\tstandup\n"


class TagsAcceptance(unittest.TestCase):
    def log(self, text: str = "") -> Any:
        log = Log(text)
        self.addCleanup(log.close)
        return log

    def added(self, log: Any, *argv: str) -> None:
        done = log.run("add", *argv)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_tags_are_a_fifth_field_in_the_order_given_each_once(self) -> None:
        log = self.log()
        self.added(log, "2026-09-02", "acme", "60", "call", "--tag", "meeting", "--tag", "billable")
        self.added(log, "2026-09-03", "acme", "30", "--tag", "b", "--tag", "a", "--tag", "b")
        self.added(log, "2026-09-03", "beta", "45")
        self.assertEqual(
            log.text(),
            "2026-09-02\tacme\t60\tcall\tmeeting,billable\n"
            "2026-09-03\tacme\t30\t\tb,a\n"
            "2026-09-03\tbeta\t45\t\n",
        )

    def test_the_report_totals_one_tag_within_the_range(self) -> None:
        log = self.log()
        self.added(log, "2026-09-02", "acme", "60", "--tag", "meeting", "--tag", "billable")
        self.added(log, "2026-09-03", "acme", "30", "--tag", "billable")
        self.added(log, "2026-09-03", "beta", "45", "--tag", "billable")
        self.added(log, "2026-09-04", "beta", "20")
        billable = log.run("report", "--tag", "billable")
        self.assertEqual(billable.returncode, 0, billable.stderr)
        self.assertEqual(
            rows(billable.stdout), [["acme", "1:30"], ["beta", "0:45"], ["total", "2:15"]]
        )
        meeting = log.run("report", "--tag", "meeting", "--from", "2026-09-03")
        self.assertEqual((meeting.returncode, meeting.stdout.strip()), (0, "no entries"))
        every = log.run("report")
        self.assertEqual(
            rows(every.stdout), [["acme", "1:30"], ["beta", "1:05"], ["total", "2:35"]]
        )

    def test_a_log_written_before_tags_reads_and_keeps_its_lines(self) -> None:
        log = self.log(BEFORE)
        self.added(log, "2026-09-02", "acme", "60", "--tag", "billable")
        self.assertEqual(log.text(), BEFORE + "2026-09-02\tacme\t60\t\tbillable\n")
        every = log.run("report")
        self.assertEqual(
            rows(every.stdout), [["acme", "1:30"], ["beta", "0:15"], ["total", "1:45"]]
        )
        billable = log.run("report", "--tag", "billable")
        self.assertEqual(rows(billable.stdout), [["acme", "1:00"], ["total", "1:00"]])

    def test_a_tag_of_the_allowed_characters_is_recorded(self) -> None:
        log = self.log()
        self.added(log, "2026-09-02", "acme", "60", "--tag", "x-1", "--tag", "a" * 20)
        self.assertEqual(log.text(), f"2026-09-02\tacme\t60\t\tx-1,{'a' * 20}\n")

    def test_any_other_tag_exits_2_and_writes_nothing(self) -> None:
        for tag in ("Bad", "a_b", "a,b", "a b", "a" * 21, ""):
            with self.subTest(tag=tag):
                log = self.log(BEFORE)
                done = log.run("add", "2026-09-02", "acme", "60", "--tag", "ok", "--tag", tag)
                self.assertEqual(done.returncode, 2, done.stdout)
                self.assertIn(f"timelog: invalid tag: {tag!r}", done.stderr)
                self.assertEqual(log.text(), BEFORE)


if __name__ == "__main__":
    unittest.main()
