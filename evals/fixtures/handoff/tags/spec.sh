# The spec package's executable part for ticket #9, written into the workspace from its root
# before the seed commit: the stubs, `Entry.tags` and the `tag` parameter of
# `report.totals`, and the package's fixed tests, each failing on the seed for the reason the
# package names.
python3 - <<'PY'
from pathlib import Path

entries = Path("entries.py")
entries.write_text(
    entries.read_text(encoding="utf-8").replace(
        '    """Time spent on a project on one day."""\n',
        '    """Time spent on a project on one day, and its tags: in the order given, each\n'
        '    once, each 1 to 20 characters of a-z, 0-9 and `-`."""\n',
    ).replace(
        '    note: str = ""\n',
        '    note: str = ""\n    tags: tuple[str, ...] = ()\n',
    ),
    encoding="utf-8",
)

report = Path("report.py")
report.write_text(
    report.read_text(encoding="utf-8").replace(
        '''def totals(entries, start=None, end=None):
    """Minutes per project over the entries from `start` to `end`, both days included; None
    leaves that side open."""
    found = {}
''',
        '''def totals(entries, start=None, end=None, tag: str | None = None):
    """Minutes per project over the entries from `start` to `end`, both days included, that
    carry `tag`; None leaves that side open, or takes every entry."""
    if tag is not None:
        raise NotImplementedError("ticket #9: totals by tag")
    found = {}
''',
    ),
    encoding="utf-8",
)
PY
cat > tests/test_tags.py <<'PY'
"""Ticket #9: tags on entries, and the report of one tag.

These tests are the hand-off package's, and they are fixed: make them pass, and change or
remove none of them.
"""

import contextlib
import io
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import report
import store
import timelog
from entries import Entry

BEFORE = "2026-09-01\tacme\t30\t\n"


def run(log, *argv):
    """timelog's exit status, standard output and standard error, with `log` as its log."""
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch.dict(os.environ, {"TIMELOG": str(log)}),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        try:
            status = timelog.main(list(argv))
        except SystemExit as stop:
            status = stop.code
    return status, out.getvalue(), err.getvalue()


class TagLineTest(unittest.TestCase):
    def test_tags_make_a_fifth_field_and_no_tags_keep_four(self):
        tagged = Entry(date(2026, 9, 2), "acme", 60, "call", ("meeting", "billable"))
        self.assertEqual(store.format_line(tagged), "2026-09-02\tacme\t60\tcall\tmeeting,billable")
        plain = Entry(date(2026, 9, 3), "beta", 45)
        self.assertEqual(store.format_line(plain), "2026-09-03\tbeta\t45\t")

    def test_five_fields_read_as_tags_four_as_none_and_six_as_an_error(self):
        line = "2026-09-02\tacme\t60\tcall\tmeeting,billable"
        self.assertEqual(
            store.parse_line(line, 1),
            Entry(date(2026, 9, 2), "acme", 60, "call", ("meeting", "billable")),
        )
        self.assertEqual(store.parse_line("2026-09-03\tbeta\t45\t", 2).tags, ())
        with self.assertRaisesRegex(store.LogError, "line 3: expected 4 fields, found 6"):
            store.parse_line(line + "\textra", 3)


class TotalsByTagTest(unittest.TestCase):
    def test_totals_count_only_the_entries_carrying_the_tag(self):
        entries = [
            Entry(date(2026, 9, 1), "acme", 60, "", ("billable",)),
            Entry(date(2026, 9, 2), "acme", 30),
            Entry(date(2026, 9, 3), "beta", 45, "", ("billable", "meeting")),
        ]
        self.assertEqual(report.totals(entries, tag="billable"), {"acme": 60, "beta": 45})
        self.assertEqual(
            report.totals(entries, start=date(2026, 9, 2), tag="billable"), {"beta": 45}
        )
        self.assertEqual(report.totals(entries, tag="travel"), {})
        self.assertEqual(report.totals(entries), {"acme": 90, "beta": 45})


class TagCommandTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.log = Path(directory.name) / "timelog.tsv"

    def test_add_writes_tags_in_the_order_given_each_once(self):
        status, _out, err = run(
            self.log, "add", "2026-09-02", "acme", "60", "call",
            "--tag", "meeting", "--tag", "billable", "--tag", "meeting",
        )
        self.assertEqual(status, 0, err)
        self.assertEqual(
            self.log.read_text(encoding="utf-8"), "2026-09-02\tacme\t60\tcall\tmeeting,billable\n"
        )

    def test_add_takes_a_tag_of_the_allowed_characters_and_refuses_any_other(self):
        status, _out, err = run(self.log, "add", "2026-09-02", "acme", "60", "--tag", "x-1")
        self.assertEqual(status, 0, err)
        written = self.log.read_text(encoding="utf-8")
        for tag in ("Bad", "a_b", "a,b", "a" * 21, ""):
            with self.subTest(tag=tag):
                status, _out, err = run(self.log, "add", "2026-09-03", "acme", "5", "--tag", tag)
                self.assertEqual(status, 2)
                self.assertEqual(err, f"timelog: invalid tag: {tag!r}\n")
                self.assertEqual(self.log.read_text(encoding="utf-8"), written)

    def test_a_log_written_before_tags_keeps_its_lines(self):
        self.log.write_text(BEFORE, encoding="utf-8")
        status, _out, err = run(self.log, "add", "2026-09-02", "acme", "60", "--tag", "billable")
        self.assertEqual(status, 0, err)
        self.assertEqual(
            self.log.read_text(encoding="utf-8"), BEFORE + "2026-09-02\tacme\t60\t\tbillable\n"
        )

    def test_report_totals_one_tag(self):
        self.log.write_text(
            BEFORE + "2026-09-02\tacme\t60\tcall\tmeeting,billable\n"
            "2026-09-03\tbeta\t45\t\tbillable\n",
            encoding="utf-8",
        )
        status, out, err = run(self.log, "report", "--tag", "billable")
        self.assertEqual(status, 0, err)
        self.assertEqual(
            [line.split() for line in out.splitlines()],
            [["acme", "1:00"], ["beta", "0:45"], ["total", "1:45"]],
        )
        status, out, err = run(self.log, "report", "--tag", "meeting", "--from", "2026-09-03")
        self.assertEqual((status, out), (0, "no entries\n"), err)


if __name__ == "__main__":
    unittest.main()
PY
