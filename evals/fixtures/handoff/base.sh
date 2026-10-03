# The hand-off fixtures' shared repository, written into the current directory: `timelog`, a
# small command line that records time spent on projects in a tab-separated log and reports
# it, an invoicing script that reads the report as JSON, unit tests, two format documents, a
# declared ticket store with its claims plan, and the ticket template. Sourced by build.sh,
# which adds the variant's own files and commits.
#
# The code is correct as written here; each ticket asks for new behaviour, not a fix.

mkdir -p tests docs .github/ISSUE_TEMPLATE .outcomebound

cat > entries.py <<'PY'
"""One entry of the time log."""

from datetime import date
from typing import NamedTuple


class Entry(NamedTuple):
    """Time spent on a project on one day."""

    day: date
    project: str
    minutes: int
    note: str = ""
PY

cat > durations.py <<'PY'
"""Durations as the command line writes them."""


def parse_duration(text):
    """The whole minutes `text` names, written as minutes alone: `90`.

    Space around the text is ignored. Raises ValueError naming the text as written where it
    names no positive whole number of minutes.
    """
    written = text.strip()
    if not written.isascii() or not written.isdigit() or int(written) == 0:
        raise ValueError(f"invalid duration: {text!r}")
    return int(written)


def format_minutes(minutes):
    """`minutes` as hours and minutes: 90 is `1:30`."""
    hours, rest = divmod(minutes, 60)
    return f"{hours}:{rest:02d}"
PY

cat > store.py <<'PY'
"""The time log on disk: one entry a line, as docs/log-format.md describes."""

from datetime import date
from pathlib import Path

from entries import Entry

FIELDS = 4


class LogError(ValueError):
    """A line of the log that cannot be read."""


def format_line(entry):
    """The entry as one line of the log, without its line end."""
    return "\t".join((entry.day.isoformat(), entry.project, str(entry.minutes), entry.note))


def parse_line(line, number):
    """The entry one line of the log holds; `number` names the line in an error."""
    fields = line.split("\t")
    if len(fields) != FIELDS:
        raise LogError(f"line {number}: expected {FIELDS} fields, found {len(fields)}")
    day, project, minutes, note = fields
    try:
        return Entry(date.fromisoformat(day), project, int(minutes), note)
    except ValueError as error:
        raise LogError(f"line {number}: {error}") from None


def load(path):
    """Every entry in the log at `path`, in the order written; none where there is no log."""
    path = Path(path)
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if line.strip():
                entries.append(parse_line(line.rstrip("\n"), number))
    return entries


def append(path, entry):
    """Add `entry` at the end of the log at `path`, creating the log where there is none."""
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(format_line(entry) + "\n")
PY

cat > report.py <<'PY'
"""Totals per project, and the report printed from them."""

from durations import format_minutes


def totals(entries, start=None, end=None):
    """Minutes per project over the entries from `start` to `end`, both days included; None
    leaves that side open."""
    found = {}
    for entry in entries:
        if start is not None and entry.day < start:
            continue
        if end is not None and entry.day > end:
            continue
        found[entry.project] = found.get(entry.project, 0) + entry.minutes
    return found


def render(found):
    """One line per project, sorted by name, then the total; `no entries` where there are
    none."""
    if not found:
        return "no entries"
    width = max(len("total"), *(len(project) for project in found))
    lines = [
        f"{project:<{width}}  {format_minutes(minutes):>6}"
        for project, minutes in sorted(found.items())
    ]
    lines.append(f"{'total':<{width}}  {format_minutes(sum(found.values())):>6}")
    return "\n".join(lines)
PY

cat > timelog.py <<'PY'
"""timelog: record time spent on projects, and report it.

    python3 timelog.py add DATE PROJECT DURATION [NOTE]
    python3 timelog.py report [--from DATE] [--to DATE]

The log is the file $TIMELOG names, or timelog.tsv in the current directory.
"""

import argparse
import os
import sys
from datetime import date

import report
import store
from durations import format_minutes, parse_duration
from entries import Entry


def log_path():
    """The log this run reads and writes."""
    return os.environ.get("TIMELOG") or "timelog.tsv"


def parser():
    commands = argparse.ArgumentParser(
        prog="timelog", description="Record time spent on projects, and report it."
    )
    verbs = commands.add_subparsers(dest="verb", required=True)
    add = verbs.add_parser("add", help="record time spent on a project")
    add.add_argument("day", type=date.fromisoformat, metavar="DATE")
    add.add_argument("project")
    add.add_argument("duration", help="the time spent, such as 90")
    add.add_argument("note", nargs="?", default="")
    shown = verbs.add_parser("report", help="total the time per project")
    shown.add_argument("--from", dest="start", type=date.fromisoformat, metavar="DATE")
    shown.add_argument("--to", dest="end", type=date.fromisoformat, metavar="DATE")
    return commands


def add(options):
    """Record the entry the options name, or raise ValueError saying why not."""
    written = options.project + options.note
    if not options.project or "\t" in written or "\n" in written:
        raise ValueError("a project is not empty, and no project or note holds a tab or line end")
    entry = Entry(options.day, options.project, parse_duration(options.duration), options.note)
    store.append(log_path(), entry)
    print(f"added {format_minutes(entry.minutes)} to {entry.project} on {entry.day}")


def main(argv=None):
    options = parser().parse_args(argv)
    try:
        if options.verb == "add":
            add(options)
        else:
            found = report.totals(store.load(log_path()), options.start, options.end)
            print(report.render(found))
    except ValueError as error:
        print(f"timelog: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY

cat > invoice.py <<'PY'
"""invoice: the invoice for a time report, read as JSON on standard input.

    python3 invoice.py --rate EUROS < report.json

The report is the shape docs/report-json.md gives. The invoice is the period, then one line
per project with its time and its amount at the hourly rate, then the total; `nothing to
bill` where the report holds no project. Input of any other shape exits 1, naming what is
wrong.
"""

import argparse
import json
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from durations import format_minutes

KEYS = {"from", "to", "projects", "total_minutes"}
PROJECT_KEYS = {"project", "minutes"}


def _whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_side(report, side):
    value = report[side]
    if value is not None and not isinstance(value, str):
        raise ValueError(f"`{side}` is a date written YYYY-MM-DD, or null")
    if value is not None:
        date.fromisoformat(value)


def _check_project(item):
    if not isinstance(item, dict) or set(item) != PROJECT_KEYS:
        raise ValueError("each project is an object with exactly the keys minutes, project")
    if not isinstance(item["project"], str) or not item["project"]:
        raise ValueError("a project's name is a string that is not empty")
    if not _whole(item["minutes"]) or item["minutes"] <= 0:
        raise ValueError(f"{item['project']}: `minutes` is a positive whole number")


def read_report(text):
    """The report `text` holds, checked against the shape; ValueError naming what is wrong."""
    report = json.loads(text)
    if not isinstance(report, dict) or set(report) != KEYS:
        raise ValueError("a report is an object with exactly the keys " + ", ".join(sorted(KEYS)))
    _check_side(report, "from")
    _check_side(report, "to")
    projects = report["projects"]
    if not isinstance(projects, list):
        raise ValueError("`projects` is a list")
    for item in projects:
        _check_project(item)
    names = [item["project"] for item in projects]
    if names != sorted(set(names)):
        raise ValueError("`projects` is sorted by name, each project once")
    total = report["total_minutes"]
    if not _whole(total) or total != sum(item["minutes"] for item in projects):
        raise ValueError("`total_minutes` is the sum of the projects' minutes")
    return report


def amount(minutes, rate):
    """What `minutes` cost at `rate` euros an hour, to the cent."""
    return (Decimal(minutes) * rate / 60).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def invoice(report, rate):
    """The invoice's text for a checked report at `rate` euros an hour."""
    lines = [f"period {report['from'] or 'start'} to {report['to'] or 'end'}"]
    if not report["projects"]:
        return "\n".join([*lines, "nothing to bill"])
    for item in report["projects"]:
        time, cost = format_minutes(item["minutes"]), amount(item["minutes"], rate)
        lines.append(f"{item['project']:<16} {time:>6} {cost:>10}")
    total = report["total_minutes"]
    lines.append(f"{'total':<16} {format_minutes(total):>6} {amount(total, rate):>10}")
    return "\n".join(lines)


def main(argv=None):
    options = argparse.ArgumentParser(prog="invoice", description="Invoice a time report.")
    options.add_argument("--rate", type=Decimal, required=True, help="euros an hour")
    arguments = options.parse_args(argv)
    try:
        report = read_report(sys.stdin.read())
    except ValueError as error:
        print(f"invoice: {error}", file=sys.stderr)
        return 1
    print(invoice(report, arguments.rate))
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY

cat > tests/test_durations.py <<'PY'
import unittest

from durations import format_minutes, parse_duration


class ParseDurationTest(unittest.TestCase):
    def test_whole_minutes(self):
        self.assertEqual(parse_duration("90"), 90)

    def test_space_around_is_ignored(self):
        self.assertEqual(parse_duration(" 45 "), 45)

    def test_no_time_is_refused(self):
        with self.assertRaisesRegex(ValueError, "invalid duration: '0'"):
            parse_duration("0")

    def test_words_are_refused(self):
        with self.assertRaises(ValueError):
            parse_duration("soon")


class FormatMinutesTest(unittest.TestCase):
    def test_hours_and_minutes(self):
        self.assertEqual(format_minutes(90), "1:30")

    def test_under_an_hour(self):
        self.assertEqual(format_minutes(5), "0:05")


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_store.py <<'PY'
import tempfile
import unittest
from datetime import date
from pathlib import Path

import store
from entries import Entry


class StoreTest(unittest.TestCase):
    def test_entries_read_back_as_written(self):
        written = [
            Entry(date(2026, 9, 1), "acme", 90, "kickoff"),
            Entry(date(2026, 9, 2), "beta", 30),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timelog.tsv"
            for entry in written:
                store.append(path, entry)
            self.assertEqual(store.load(path), written)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "2026-09-01\tacme\t90\tkickoff\n2026-09-02\tbeta\t30\t\n",
            )

    def test_no_log_is_no_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(store.load(Path(directory) / "timelog.tsv"), [])

    def test_a_line_with_too_few_fields_names_its_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timelog.tsv"
            path.write_text("2026-09-01\tacme\t90\t\n2026-09-02\tbeta\n", encoding="utf-8")
            with self.assertRaisesRegex(store.LogError, "line 2: expected 4 fields, found 2"):
                store.load(path)


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_report.py <<'PY'
import unittest
from datetime import date

import report
from entries import Entry

ENTRIES = [
    Entry(date(2026, 8, 31), "acme", 60),
    Entry(date(2026, 9, 1), "acme", 90),
    Entry(date(2026, 9, 15), "beta", 45),
]


class ReportTest(unittest.TestCase):
    def test_totals_per_project(self):
        self.assertEqual(report.totals(ENTRIES), {"acme": 150, "beta": 45})

    def test_the_range_includes_both_days(self):
        found = report.totals(ENTRIES, date(2026, 9, 1), date(2026, 9, 15))
        self.assertEqual(found, {"acme": 90, "beta": 45})

    def test_the_report_lists_projects_by_name_then_the_total(self):
        self.assertEqual(
            report.render({"beta": 45, "acme": 90}),
            "acme     1:30\nbeta     0:45\ntotal    2:15",
        )

    def test_an_empty_report_says_so(self):
        self.assertEqual(report.render({}), "no entries")


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_cli.py <<'PY'
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import timelog


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


class CommandTest(unittest.TestCase):
    def test_add_then_report(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "timelog.tsv"
            self.assertEqual(run(log, "add", "2026-09-01", "acme", "90", "kickoff")[0], 0)
            self.assertEqual(run(log, "add", "2026-09-02", "beta", "45")[0], 0)
            status, out, _err = run(log, "report", "--from", "2026-09-01")
            self.assertEqual(status, 0)
            self.assertEqual(out, "acme     1:30\nbeta     0:45\ntotal    2:15\n")

    def test_a_bad_duration_exits_2_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "timelog.tsv"
            status, _out, err = run(log, "add", "2026-09-01", "acme", "soon")
            self.assertEqual((status, err), (2, "timelog: invalid duration: 'soon'\n"))
            self.assertFalse(log.exists())


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_invoice.py <<'PY'
import json
import unittest
from decimal import Decimal

import invoice

REPORT = {
    "from": "2026-09-01",
    "to": "2026-09-30",
    "projects": [{"project": "acme", "minutes": 90}, {"project": "beta", "minutes": 45}],
    "total_minutes": 135,
}


class InvoiceTest(unittest.TestCase):
    def test_one_line_per_project_then_the_total(self):
        report = invoice.read_report(json.dumps(REPORT))
        self.assertEqual(
            invoice.invoice(report, Decimal("80")).splitlines(),
            [
                "period 2026-09-01 to 2026-09-30",
                "acme               1:30     120.00",
                "beta               0:45      60.00",
                "total              2:15     180.00",
            ],
        )

    def test_a_total_that_is_not_the_sum_is_refused(self):
        with self.assertRaisesRegex(ValueError, "total_minutes"):
            invoice.read_report(json.dumps({**REPORT, "total_minutes": 100}))

    def test_minutes_written_as_text_are_refused(self):
        wrong = {**REPORT, "projects": [{"project": "acme", "minutes": "1:30"}]}
        with self.assertRaisesRegex(ValueError, "positive whole number"):
            invoice.read_report(json.dumps(wrong))


if __name__ == "__main__":
    unittest.main()
PY

cat > docs/log-format.md <<'MD'
# The log format

## Lines

The log is UTF-8 text, one entry a line, each line ending in a line feed. A line holds four
fields separated by tabs, in this order: the day, written `YYYY-MM-DD`; the project; the
minutes, a positive whole number; and the note, which may be empty. No field holds a tab or a
line end. Blank lines are skipped.

## Reading

`store.load` reads the log line by line. A line it cannot read stops the read with
`line N: <reason>`, and `timelog` exits 2 printing it.
MD

cat > docs/report-json.md <<'MD'
# The report as JSON

`invoice.py` reads a time report in this shape on its standard input, and refuses any other.

## Shape

One JSON object with exactly four keys:

- `from`: the first day the report covers, written `YYYY-MM-DD`, or `null` where the report
  has no first day.
- `to`: the last day the report covers, written the same way, or `null` where it has no last
  day.
- `projects`: a list holding one object for each project with time in the report, sorted by
  project name. Each object has exactly two keys: `project`, the project's name, and
  `minutes`, its time as a positive whole number of minutes.
- `total_minutes`: the sum of the projects' minutes, which is 0 where the list is empty.

For example:

```json
{
  "from": "2026-09-01",
  "to": "2026-09-30",
  "projects": [{"project": "acme", "minutes": 90}, {"project": "beta", "minutes": 45}],
  "total_minutes": 135
}
```
MD

cat > README.md <<'MD'
# timelog

Record the time you spend on projects, and report it.

## Usage

```sh
python3 timelog.py add 2026-09-01 acme 90 "kickoff call"
python3 timelog.py report --from 2026-09-01 --to 2026-09-30
```

`add` records the minutes spent on a project on a day, with an optional note. `report`
prints the time per project, then the total. The log is the file `$TIMELOG` names, or
`timelog.tsv` in the current directory; `docs/log-format.md` describes it.

`invoice.py` prints the invoice for a report given as JSON in the shape
`docs/report-json.md` describes: `python3 invoice.py --rate 90 < report.json`.
MD

cat > .gitignore <<'TXT'
__pycache__/
timelog.tsv
TXT

cat > CONTRIBUTING.md <<'MD'
# Contributing

## Tickets

Tickets live on the tracker that `.outcomebound/tickets.json` declares, and each accepted
ticket is built in this checkout. The tests are `python3 -B -m unittest discover -s tests`.

## How work lands

Leave the change uncommitted in the working tree: a maintainer reviews it and commits it with
the ticket's number.
MD

cat > AGENTS.md <<'NOTE'
# timelog

`timelog.py` records time spent on projects in a log and reports it; `invoice.py` invoices a
report. Run the tests with `python3 -B -m unittest discover -s tests`. How tickets are built
and how work lands is in `CONTRIBUTING.md`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

cat > .github/ISSUE_TEMPLATE/ticket.md <<'MD'
## Outcome

## Design

## Limits

<!-- outcomebound:begin id=ticket v=1 -->
reads:
bounds:
human-only: no
done-when:
<!-- outcomebound:end id=ticket -->
MD

cat > .outcomebound/tickets.json <<'JSON'
{
 "version": 1,
 "store": "github",
 "repo": "example/timelog",
 "label": "ob-ticket",
 "human_label": "human-only",
 "request_label": "human-requested",
 "claims": ".outcomebound/ticket-claims.json",
 "default_branch": "main"
}
JSON

cat > .outcomebound/ticket-claims.json <<'JSON'
{
 "version": 1,
 "cwd": ".",
 "claims": [
  {
   "name": "timelog-tests",
   "risk": "a change breaks what timelog records, reports or invoices",
   "kind": "test",
   "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
   "required_paths": ["timelog.py", "tests"]
  }
 ]
}
JSON
