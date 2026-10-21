# The corelib replica's project files, written into the current directory in their final form:
# `tally`, a small Python library and command line for time entries, with a public contract
# (docs/specs/contract/), recorded output decisions (docs/specs/output/decisions.md), proof gates
# under gates/, tickets, a changelog with contract versions and a slow integration suite.
# base.sh sources this, then builds the history from these files.

mkdir -p tally tests/integration gates tools docs/specs/contract docs/specs/output tickets \
  .github/workflows

cat > tally/__init__.py <<'PY'
"""tally: read time entries and report on them."""

__version__ = "3.2.0"
# The version of the public contract, docs/specs/contract/design.md. The changelog names the
# contract of each release, and gates/contract_version.py holds the three together.
CONTRACT_VERSION = 3
PY

cat > tally/__main__.py <<'PY'
from tally.cli import main

raise SystemExit(main())
PY

cat > tally/errors.py <<'PY'
"""Errors, and the two forms the command line writes them in (decision D-04 in
docs/specs/output/decisions.md)."""

import json

# Every code the package raises, with what it means; docs/specs/contract/errors.md lists the same.
CODES = {
    "E101": "an input file cannot be read",
    "E102": "a value in an entry is invalid",
    "E103": "an input file lacks a required column",
    "E104": "an option has an invalid value",
}


class TallyError(Exception):
    """A failure the command line reports to the person, with a code from CODES."""

    def __init__(
        self, code: str, message: str, source: str = "", line: int = 0, field: str = ""
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.source = source
        self.line = line
        self.field = field

    def __str__(self) -> str:
        return format_text(self)


def format_text(error: TallyError) -> str:
    """The text form: `error[E102] entries.csv:4: minutes: must be ...`, leaving out the parts
    that do not apply."""

    place = f"{error.source}:{error.line}" if error.source and error.line else error.source
    rest = ": ".join(part for part in (place, error.field, error.message) if part)
    return f"error[{error.code}] {rest}"


def as_record(error: TallyError) -> dict:
    """The error as a mapping with every key present, for machine output."""

    return {
        "code": error.code,
        "source": error.source,
        "line": error.line,
        "field": error.field,
        "message": error.message,
    }


def format_json(error: TallyError) -> str:
    """The machine form: one JSON object on one line, `{"error": {...}}`."""

    return json.dumps({"error": as_record(error)}, sort_keys=True)
PY

cat > tally/model.py <<'PY'
"""A time entry, and turning a row of an input file into one."""

import re
from dataclasses import dataclass
from datetime import date

from tally.errors import TallyError

# The columns of an input file, in the order tally writes them; `note` may be left out.
COLUMNS = ("day", "project", "person", "minutes", "note")
REQUIRED = ("day", "project", "person", "minutes")
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_MINUTES = 24 * 60


@dataclass(frozen=True, order=True)
class Entry:
    """Time one person spent on one project on one day."""

    day: date
    project: str
    person: str
    minutes: int
    note: str = ""


def parse_day(text: str, source: str = "", line: int = 0, field: str = "day") -> date:
    """The day `text` names in YYYY-MM-DD form; TallyError E102 otherwise."""

    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        message = f"not a day in YYYY-MM-DD form: {text.strip()!r}"
        raise TallyError("E102", message, source, line, field) from None


def _name(row: dict, column: str, source: str, line: int) -> str:
    value = str(row.get(column) or "").strip()
    if not NAME.match(value):
        message = "must be lower-case letters, digits and dashes"
        raise TallyError("E102", message, source, line, column)
    return value


def parse_row(row: dict, source: str = "", line: int = 0) -> Entry:
    """The entry a row holds, a row being a mapping of column to text. TallyError E102 names the
    first invalid value, in column order."""

    day = parse_day(str(row.get("day") or ""), source, line)
    project = _name(row, "project", source, line)
    person = _name(row, "person", source, line)
    text = str(row.get("minutes") or "").strip()
    if not text.isdigit() or not 0 < int(text) <= MAX_MINUTES:
        message = f"must be a whole number from 1 to {MAX_MINUTES}"
        raise TallyError("E102", message, source, line, "minutes")
    return Entry(day, project, person, int(text), str(row.get("note") or "").strip())


def to_row(entry: Entry) -> dict:
    """The row `parse_row` reads back as `entry`."""

    return {
        "day": entry.day.isoformat(),
        "project": entry.project,
        "person": entry.person,
        "minutes": str(entry.minutes),
        "note": entry.note,
    }
PY

cat > tally/readers.py <<'PY'
"""Reading entries from CSV and JSON Lines files, and writing them as CSV."""

import csv
import json
from pathlib import Path

from tally.errors import TallyError
from tally.model import COLUMNS, REQUIRED, Entry, parse_row, to_row


def rows(path: str | Path) -> list:
    """Each (line number, row) of the file at `path`, a row being a mapping of column to text.

    A CSV file's header is line 1, so its first entry is on line 2; a JSON Lines file's first
    entry is on line 1. TallyError E101 where the file cannot be read, E103 where a CSV file's
    header lacks a required column.
    """

    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as problem:
        raise TallyError("E101", problem.strerror or "cannot be read", str(path)) from None
    if path.suffix == ".jsonl":
        return list(_jsonl_rows(text, str(path)))
    return list(_csv_rows(text, str(path)))


def _csv_rows(text: str, source: str):
    reader = csv.DictReader(text.splitlines())
    names = reader.fieldnames or []
    for column in REQUIRED:
        if column not in names:
            raise TallyError("E103", "the header lacks this column", source, 1, column)
    for row in reader:
        yield reader.line_num, row


def _jsonl_rows(text: str, source: str):
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if not isinstance(row, dict):
            raise TallyError("E102", "not a JSON object", source, number)
        yield number, {key: "" if value is None else str(value) for key, value in row.items()}


def read(path: str | Path) -> list[Entry]:
    """The entries of one file; TallyError at the first problem."""

    return [parse_row(row, str(path), number) for number, row in rows(path)]


def read_all(paths) -> list[Entry]:
    """The entries of every file, in the order given."""

    entries = []
    for path in paths:
        entries.extend(read(path))
    return entries


def write_csv(entries, path: str | Path) -> None:
    """Write `entries` as a CSV file with the standard columns."""

    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for entry in entries:
            writer.writerow(to_row(entry))
PY

cat > tally/aggregate.py <<'PY'
"""Grouping entries by project, person, ISO week or day."""

from dataclasses import dataclass
from datetime import date

from tally.errors import TallyError
from tally.model import Entry

GROUPINGS = ("project", "person", "week", "day")


@dataclass(frozen=True)
class Group:
    """The entries that share one key: how many there are and their minutes."""

    key: str
    entry_count: int
    minutes: int


def week_of(day: date) -> str:
    """The ISO week of `day`, as `2026-W14` (decision D-02)."""

    year, week, _weekday = day.isocalendar()
    return f"{year}-W{week:02d}"


def key_of(entry: Entry, by: str) -> str:
    """The key `entry` is grouped under."""

    if by == "project":
        return entry.project
    if by == "person":
        return entry.person
    if by == "week":
        return week_of(entry.day)
    if by == "day":
        return entry.day.isoformat()
    message = f"unknown grouping {by!r}; use one of {', '.join(GROUPINGS)}"
    raise TallyError("E104", message, field="by")


def group(entries, by: str) -> list[Group]:
    """One group for each key, in key order."""

    counts: dict[str, int] = {}
    minutes: dict[str, int] = {}
    for entry in entries:
        key = key_of(entry, by)
        counts[key] = counts.get(key, 0) + 1
        minutes[key] = minutes.get(key, 0) + entry.minutes
    return [Group(key, counts[key], minutes[key]) for key in sorted(counts)]


def total_minutes(groups) -> int:
    return sum(item.minutes for item in groups)


def total_entries(groups) -> int:
    return sum(item.entry_count for item in groups)
PY

cat > tally/report.py <<'PY'
"""The report: entries grouped into rows, and the text table the command line prints."""

from tally import aggregate


def build(entries, by: str = "project") -> list[aggregate.Group]:
    """The report's rows: one group for each key of the grouping `by`."""

    return aggregate.group(entries, by)


def hours(minutes: int) -> str:
    """Minutes as hours and minutes, `h:mm`, the form text output uses (decision D-01)."""

    return f"{minutes // 60}:{minutes % 60:02d}"


def render_text(groups, by: str = "project") -> str:
    """The text table: a header, a line for each group, then the total."""

    width = max([len(by), len("total"), *(len(item.key) for item in groups)])
    lines = [f"{by:<{width}}  {'entries':>7}  {'hours':>8}"]
    for item in groups:
        lines.append(f"{item.key:<{width}}  {item.entry_count:>7}  {hours(item.minutes):>8}")
    entries = aggregate.total_entries(groups)
    minutes = aggregate.total_minutes(groups)
    lines.append(f"{'total':<{width}}  {entries:>7}  {hours(minutes):>8}")
    return "\n".join(lines) + "\n"
PY

cat > tally/validate.py <<'PY'
"""Checking input files: every problem in every file, where reading stops at the first."""

from tally.errors import TallyError
from tally.model import parse_row
from tally.readers import rows


def check(paths) -> tuple[int, list[TallyError]]:
    """The number of valid entries, and each problem found, in file order.

    A file whose header lacks a column is one problem, and its rows are not checked. A file that
    cannot be read is not a finding but an error: TallyError E101 is raised.
    """

    count, problems = 0, []
    for path in paths:
        try:
            found = rows(path)
        except TallyError as problem:
            if problem.code == "E101":
                raise
            problems.append(problem)
            continue
        for number, row in found:
            try:
                parse_row(row, str(path), number)
            except TallyError as problem:
                problems.append(problem)
            else:
                count += 1
    return count, problems
PY

cat > tally/merge.py <<'PY'
"""Merging entry files into one, dropping exact duplicates."""

from tally.model import Entry


def merge(entry_lists) -> tuple[list[Entry], int]:
    """Every distinct entry of the lists, sorted by day, project and person, and how many exact
    duplicates were dropped."""

    seen: set[Entry] = set()
    merged: list[Entry] = []
    dropped = 0
    for entries in entry_lists:
        for entry in entries:
            if entry in seen:
                dropped += 1
                continue
            seen.add(entry)
            merged.append(entry)
    merged.sort()
    return merged, dropped
PY

cat > tally/cli.py <<'PY'
"""The command line: python3 -m tally <command>. docs/cli.md is its reference."""

import argparse
import json
import sys

from tally import CONTRACT_VERSION, __version__, aggregate, errors, merge, readers, report, validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tally", description="Read time entries and report.")
    commands = parser.add_subparsers(dest="command", required=True)

    reporting = commands.add_parser("report", help="total the entries of FILEs by a grouping")
    reporting.add_argument("files", nargs="+", metavar="FILE")
    reporting.add_argument("--by", default="project", choices=aggregate.GROUPINGS)

    checking = commands.add_parser("validate", help="list every problem in FILEs")
    checking.add_argument("files", nargs="+", metavar="FILE")
    checking.add_argument("--output", default="text", choices=("text", "json"))

    merging = commands.add_parser("merge", help="merge FILEs into one CSV, dropping duplicates")
    merging.add_argument("files", nargs="+", metavar="FILE")
    merging.add_argument("--out", required=True, metavar="OUT", help="the CSV file to write")

    commands.add_parser("version", help="print the version and the contract version")
    return parser


def run_report(args) -> int:
    groups = report.build(readers.read_all(args.files), args.by)
    sys.stdout.write(report.render_text(groups, args.by))
    return 0


def run_validate(args) -> int:
    try:
        count, problems = validate.check(args.files)
    except errors.TallyError as error:
        if args.output != "json":
            raise
        print(errors.format_json(error), file=sys.stderr)
        return 2
    if args.output == "json":
        found = {
            "file_count": len(args.files),
            "entry_count": count,
            "problem_count": len(problems),
            "problems": [errors.as_record(problem) for problem in problems],
        }
        print(json.dumps(found, indent=2))
    else:
        for problem in problems:
            print(errors.format_text(problem))
        print(f"{len(args.files)} files, {count} valid entries, {len(problems)} problems")
    return 1 if problems else 0


def run_merge(args) -> int:
    merged, dropped = merge.merge([readers.read(path) for path in args.files])
    readers.write_csv(merged, args.out)
    print(f"merged {len(args.files)} files: {len(merged)} entries, {dropped} duplicates dropped")
    return 0


def run_version(_args) -> int:
    print(f"tally {__version__} (contract {CONTRACT_VERSION})")
    return 0


HANDLERS = {
    "report": run_report,
    "validate": run_validate,
    "merge": run_merge,
    "version": run_version,
}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except errors.TallyError as error:
        print(errors.format_text(error), file=sys.stderr)
        return 2
PY

cat > tests/__init__.py <<'PY'
PY

cat > tests/helpers.py <<'PY'
"""What the tests share: a scratch folder and input files written into it."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tally import cli

HEADER = "day,project,person,minutes,note\n"


class ScratchCase(unittest.TestCase):
    """A test with a scratch folder of its own, removed after it."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.folder = Path(scratch.name)

    def write(self, name, lines, header=HEADER):
        path = self.folder / name
        path.write_text(header + "".join(line + "\n" for line in lines), encoding="utf-8")
        return path


def run_cli(*argv):
    """The command line's exit status, stdout and stderr for `argv`."""

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            status = cli.main([str(word) for word in argv])
        except SystemExit as stop:
            status = stop.code
    return status, out.getvalue(), err.getvalue()
PY

cat > tests/test_model.py <<'PY'
import unittest
from datetime import date

from tally.errors import TallyError
from tally.model import Entry, parse_row, to_row

ROW = {"day": "2026-04-02", "project": "atlas", "person": "ana", "minutes": "90", "note": "x"}


class ParseRowTest(unittest.TestCase):
    def test_a_valid_row_is_an_entry(self):
        self.assertEqual(parse_row(ROW), Entry(date(2026, 4, 2), "atlas", "ana", 90, "x"))

    def test_the_note_may_be_left_out(self):
        row = {key: value for key, value in ROW.items() if key != "note"}
        self.assertEqual(parse_row(row).note, "")

    def test_values_are_stripped(self):
        row = {**ROW, "project": " atlas ", "minutes": " 90 "}
        self.assertEqual(parse_row(row).project, "atlas")
        self.assertEqual(parse_row(row).minutes, 90)

    def test_a_row_round_trips(self):
        self.assertEqual(parse_row(to_row(parse_row(ROW))), parse_row(ROW))

    def test_a_day_not_in_iso_form_is_refused(self):
        with self.assertRaises(TallyError) as raised:
            parse_row({**ROW, "day": "02/04/2026"}, "a.csv", 3)
        self.assertEqual((raised.exception.code, raised.exception.field), ("E102", "day"))
        self.assertEqual(raised.exception.line, 3)

    def test_a_project_with_capitals_is_refused(self):
        with self.assertRaises(TallyError) as raised:
            parse_row({**ROW, "project": "Atlas"})
        self.assertEqual(raised.exception.field, "project")

    def test_an_empty_person_is_refused(self):
        with self.assertRaises(TallyError) as raised:
            parse_row({**ROW, "person": ""})
        self.assertEqual(raised.exception.field, "person")

    def test_minutes_must_be_a_whole_number_above_zero(self):
        for bad in ("0", "-5", "1.5", "ten", ""):
            with self.subTest(minutes=bad), self.assertRaises(TallyError) as raised:
                parse_row({**ROW, "minutes": bad})
            self.assertEqual(raised.exception.field, "minutes")

    def test_minutes_cannot_pass_a_day(self):
        self.assertEqual(parse_row({**ROW, "minutes": "1440"}).minutes, 1440)
        with self.assertRaises(TallyError):
            parse_row({**ROW, "minutes": "1441"})

    def test_entries_sort_by_day_then_project_then_person(self):
        later = parse_row({**ROW, "day": "2026-04-03", "project": "aa"})
        other = parse_row({**ROW, "project": "zeta"})
        self.assertEqual(sorted([later, other, parse_row(ROW)])[0], parse_row(ROW))
        self.assertEqual(sorted([later, other])[0], other)


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_readers.py <<'PY'
import unittest

from tally import readers
from tally.errors import TallyError
from tests.helpers import ScratchCase


class ReadCsvTest(ScratchCase):
    def test_entries_are_read_in_file_order(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana,90,", "2026-04-01,borea,ben,30,call"])
        entries = readers.read(path)
        self.assertEqual([entry.project for entry in entries], ["atlas", "borea"])

    def test_an_error_names_the_line_of_the_file(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana,90,", "2026-04-02,atlas,ana,-5,"])
        with self.assertRaises(TallyError) as raised:
            readers.read(path)
        self.assertEqual((raised.exception.code, raised.exception.line), ("E102", 3))
        self.assertEqual(raised.exception.source, str(path))

    def test_a_missing_column_is_e103_on_line_1(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana"], header="day,project,person\n")
        with self.assertRaises(TallyError) as raised:
            readers.read(path)
        error = raised.exception
        self.assertEqual((error.code, error.line, error.field), ("E103", 1, "minutes"))

    def test_a_missing_file_is_e101(self):
        with self.assertRaises(TallyError) as raised:
            readers.read(self.folder / "absent.csv")
        self.assertEqual(raised.exception.code, "E101")

    def test_written_entries_read_back_the_same(self):
        entries = readers.read(self.write("a.csv", ["2026-04-02,atlas,ana,90,a note"]))
        readers.write_csv(entries, self.folder / "b.csv")
        self.assertEqual(readers.read(self.folder / "b.csv"), entries)


class ReadJsonLinesTest(ScratchCase):
    def test_json_lines_are_read(self):
        path = self.folder / "a.jsonl"
        line = '{"day": "2026-04-02", "project": "atlas", "person": "ana", "minutes": 90}'
        path.write_text(line + "\n\n", encoding="utf-8")
        self.assertEqual(readers.read(path)[0].minutes, 90)

    def test_a_line_that_is_not_an_object_is_e102(self):
        path = self.folder / "a.jsonl"
        path.write_text("[1, 2]\n", encoding="utf-8")
        with self.assertRaises(TallyError) as raised:
            readers.read(path)
        self.assertEqual((raised.exception.code, raised.exception.line), ("E102", 1))


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_aggregate.py <<'PY'
import unittest
from datetime import date

from tally import aggregate
from tally.errors import TallyError
from tally.model import Entry

ENTRIES = [
    Entry(date(2026, 3, 30), "atlas", "ana", 60),
    Entry(date(2026, 3, 31), "atlas", "ben", 30),
    Entry(date(2026, 4, 6), "borea", "ana", 45),
]


class GroupTest(unittest.TestCase):
    def test_by_project(self):
        groups = aggregate.group(ENTRIES, "project")
        self.assertEqual(
            groups, [aggregate.Group("atlas", 2, 90), aggregate.Group("borea", 1, 45)]
        )

    def test_by_person(self):
        self.assertEqual([g.key for g in aggregate.group(ENTRIES, "person")], ["ana", "ben"])

    def test_by_week(self):
        groups = aggregate.group(ENTRIES, "week")
        self.assertEqual([(g.key, g.minutes) for g in groups], [("2026-W14", 90), ("2026-W15", 45)])

    def test_by_day(self):
        self.assertEqual(aggregate.group(ENTRIES, "day")[0].key, "2026-03-30")

    def test_totals(self):
        groups = aggregate.group(ENTRIES, "project")
        self.assertEqual((aggregate.total_entries(groups), aggregate.total_minutes(groups)), (3, 135))

    def test_an_unknown_grouping_is_e104(self):
        with self.assertRaises(TallyError) as raised:
            aggregate.group(ENTRIES, "month")
        self.assertEqual(raised.exception.code, "E104")


class WeekTest(unittest.TestCase):
    def test_weeks_are_iso_weeks_at_the_edge_of_the_year(self):
        self.assertEqual(aggregate.week_of(date(2026, 1, 1)), "2026-W01")
        self.assertEqual(aggregate.week_of(date(2027, 1, 1)), "2026-W53")
        self.assertEqual(aggregate.week_of(date(2024, 12, 30)), "2025-W01")


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_report.py <<'PY'
import unittest
from datetime import date

from tally import report
from tally.model import Entry


class HoursTest(unittest.TestCase):
    def test_hours_and_minutes(self):
        self.assertEqual([report.hours(m) for m in (0, 5, 60, 725)], ["0:00", "0:05", "1:00", "12:05"])


class RenderTextTest(unittest.TestCase):
    def test_the_table_has_a_header_a_line_a_group_and_a_total(self):
        entries = [
            Entry(date(2026, 4, 1), "atlas", "ana", 90),
            Entry(date(2026, 4, 1), "borea", "ana", 30),
            Entry(date(2026, 4, 2), "atlas", "ben", 15),
        ]
        expected = (
            "project  entries     hours\n"
            "atlas          2      1:45\n"
            "borea          1      0:30\n"
            "total          3      2:15\n"
        )
        self.assertEqual(report.render_text(report.build(entries), "project"), expected)

    def test_an_empty_report_still_has_its_total(self):
        self.assertTrue(report.render_text([], "week").endswith("total        0      0:00\n"))


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_validate.py <<'PY'
import unittest

from tally import validate
from tally.errors import TallyError
from tests.helpers import ScratchCase


class CheckTest(ScratchCase):
    def test_every_problem_in_every_file_is_found(self):
        first = self.write("a.csv", ["2026-04-02,atlas,ana,90,", "2026-04-02,Atlas,ana,90,"])
        second = self.write("b.csv", ["bad,atlas,ana,90,", "2026-04-02,atlas,ana,0,"])
        count, problems = validate.check([first, second])
        self.assertEqual(count, 1)
        self.assertEqual([(p.line, p.field) for p in problems], [(3, "project"), (2, "day"), (3, "minutes")])

    def test_a_missing_column_is_a_problem_of_that_file(self):
        first = self.write("a.csv", ["2026-04-02,atlas"], header="day,project\n")
        count, problems = validate.check([first])
        self.assertEqual((count, problems[0].code), (0, "E103"))

    def test_an_unreadable_file_is_an_error(self):
        with self.assertRaises(TallyError) as raised:
            validate.check([self.folder / "absent.csv"])
        self.assertEqual(raised.exception.code, "E101")


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_merge.py <<'PY'
import unittest
from datetime import date

from tally.merge import merge
from tally.model import Entry

ANA = Entry(date(2026, 4, 2), "atlas", "ana", 90)
BEN = Entry(date(2026, 4, 1), "atlas", "ben", 30)


class MergeTest(unittest.TestCase):
    def test_exact_duplicates_are_dropped_and_counted(self):
        merged, dropped = merge([[ANA, BEN], [ANA]])
        self.assertEqual((merged, dropped), ([BEN, ANA], 1))

    def test_entries_that_differ_in_any_field_are_kept(self):
        other = Entry(date(2026, 4, 2), "atlas", "ana", 90, "a note")
        self.assertEqual(merge([[ANA], [other]])[1], 0)


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_cli.py <<'PY'
import json
import unittest

from tests.helpers import ScratchCase, run_cli


class ReportCommandTest(ScratchCase):
    def test_the_report_prints_the_table(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana,90,"])
        status, out, _err = run_cli("report", path)
        self.assertEqual(status, 0)
        self.assertIn("atlas          1      1:30", out)

    def test_an_invalid_entry_is_an_error_line_and_status_2(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana,-5,"])
        status, out, err = run_cli("report", path, "--by", "person")
        self.assertEqual((status, out), (2, ""))
        self.assertEqual(err, f"error[E102] {path}:2: minutes: must be a whole number from 1 to 1440\n")

    def test_a_report_by_week_reads_csv_and_json_lines_together(self):
        first = self.write("a.csv", ["2026-03-30,atlas,ana,60,"])
        second = self.folder / "b.jsonl"
        line = '{"day": "2026-04-06", "project": "atlas", "person": "ben", "minutes": 30}'
        second.write_text(line + "\n", encoding="utf-8")
        status, out, _err = run_cli("report", first, second, "--by", "week")
        self.assertEqual(status, 0)
        self.assertEqual(out.splitlines()[1:3], ["2026-W14        1      1:00", "2026-W15        1      0:30"])

    def test_an_unknown_grouping_is_refused_by_the_parser(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana,90,"])
        status, _out, err = run_cli("report", path, "--by", "month")
        self.assertEqual(status, 2)
        self.assertIn("invalid choice", err)


class ValidateCommandTest(ScratchCase):
    def test_json_output_names_its_counts(self):
        path = self.write("a.csv", ["2026-04-02,atlas,ana,90,", "2026-04-02,atlas,ana,0,"])
        status, out, _err = run_cli("validate", path, "--output", "json")
        found = json.loads(out)
        self.assertEqual(status, 1)
        self.assertEqual((found["entry_count"], found["problem_count"]), (1, 1))
        self.assertEqual(found["problems"][0]["field"], "minutes")

    def test_an_unreadable_file_in_json_output_is_a_json_error_on_stderr(self):
        status, out, err = run_cli("validate", self.folder / "absent.csv", "--output", "json")
        self.assertEqual((status, out), (2, ""))
        self.assertEqual(json.loads(err)["error"]["code"], "E101")


class MergeCommandTest(ScratchCase):
    def test_merge_writes_one_file_and_says_what_it_dropped(self):
        first = self.write("a.csv", ["2026-04-02,atlas,ana,90,"])
        second = self.write("b.csv", ["2026-04-02,atlas,ana,90,", "2026-04-03,atlas,ana,30,"])
        status, out, _err = run_cli("merge", first, second, "--out", self.folder / "all.csv")
        self.assertEqual(status, 0)
        self.assertEqual(out, "merged 2 files: 2 entries, 1 duplicates dropped\n")


class VersionCommandTest(ScratchCase):
    def test_the_version_names_the_contract(self):
        status, out, _err = run_cli("version")
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("tally ") and "(contract " in out)


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/test_errors.py <<'PY'
import json
import unittest

from tally import errors
from tally.errors import TallyError


class FormatTextTest(unittest.TestCase):
    def test_every_part(self):
        error = TallyError("E102", "must be a whole number", "a.csv", 4, "minutes")
        self.assertEqual(errors.format_text(error), "error[E102] a.csv:4: minutes: must be a whole number")

    def test_the_parts_that_do_not_apply_are_left_out(self):
        self.assertEqual(
            errors.format_text(TallyError("E101", "No such file", "a.csv")),
            "error[E101] a.csv: No such file",
        )
        self.assertEqual(
            errors.format_text(TallyError("E104", "unknown grouping", field="by")),
            "error[E104] by: unknown grouping",
        )

    def test_str_is_the_text_form(self):
        error = TallyError("E101", "No such file", "a.csv")
        self.assertEqual(str(error), errors.format_text(error))


class FormatJsonTest(unittest.TestCase):
    def test_one_object_on_one_line_with_every_key(self):
        line = errors.format_json(TallyError("E101", "No such file", "a.csv"))
        self.assertNotIn("\n", line)
        found = json.loads(line)["error"]
        self.assertEqual(set(found), {"code", "source", "line", "field", "message"})
        self.assertEqual((found["line"], found["field"]), (0, ""))


class CodesTest(unittest.TestCase):
    def test_every_code_has_a_meaning(self):
        self.assertTrue(all(code.startswith("E1") and meaning for code, meaning in errors.CODES.items()))


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/integration/run_suite.py <<'PY'
"""The integration suite: a generated year of entries through every command, end to end, as the
nightly job runs them, then the dashboard importer's poll after each stage.

Run from the repository root: python3 -B tests/integration/run_suite.py
"""

import csv
import random
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

PEOPLE = [f"p{number:02d}" for number in range(40)]
PROJECTS = [f"project-{number}" for number in range(12)]
# The dashboard importer polls on a fixed interval; each stage waits for one poll, as in
# production, so a stage that leaves files half-written is seen.
POLL_SECONDS = 14


def tally(*argv, check=True):
    done = subprocess.run(
        [sys.executable, "-B", "-m", "tally", *map(str, argv)],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and done.returncode != 0:
        raise SystemExit(f"tally {' '.join(map(str, argv))} exited {done.returncode}: {done.stderr}")
    return done


def generate(folder):
    """Four quarterly files of a year of entries, with the overlap a real export has."""

    chance = random.Random(2026)
    day, files = date(2025, 1, 1), []
    for quarter in range(4):
        path = folder / f"q{quarter + 1}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["day", "project", "person", "minutes", "note"])
            for _ in range(91):
                for person in PEOPLE:
                    for _ in range(chance.randint(1, 4)):
                        project = chance.choice(PROJECTS)
                        writer.writerow([day.isoformat(), project, person, chance.randint(5, 240), ""])
                day += timedelta(days=1)
        files.append(path)
    return files


def stage(name, action):
    started = time.monotonic()
    action()
    time.sleep(POLL_SECONDS)
    print(f"integration: {name} ok ({time.monotonic() - started:.1f}s)")


def main():
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch)
        files = generate(folder)
        merged = folder / "year.csv"
        stage("validate", lambda: tally("validate", *files, "--output", "json"))
        stage("merge", lambda: tally("merge", *files, files[0], "--out", merged))

        def reports():
            totals = set()
            for by in ("project", "person", "week", "day"):
                out = tally("report", merged, "--by", by).stdout
                totals.add(out.strip().splitlines()[-1].split()[-1])
            if len(totals) != 1:
                raise SystemExit(f"the groupings disagree on the total: {sorted(totals)}")

        stage("report", reports)
        stage("errors", lambda: tally("report", folder / "absent.csv", check=False))
        stage("version", lambda: tally("version"))
    print("integration: all stages ok")


if __name__ == "__main__":
    main()
PY

cat > gates/contract_version.py <<'PY'
"""Gate: the contract version is the same in the code, in the contract document and in the
changelog's latest release, so a contract change never ships unannounced."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tally

design = (ROOT / "docs/specs/contract/design.md").read_text(encoding="utf-8")
changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
documented = re.search(r"^Contract version: (\d+)$", design, re.MULTILINE)
released = re.search(r"^## \d+\.\d+\.\d+ .*\(contract (\d+)\)", changelog, re.MULTILINE)
found = {
    "tally.CONTRACT_VERSION": str(tally.CONTRACT_VERSION),
    "docs/specs/contract/design.md": documented.group(1) if documented else "none",
    "CHANGELOG.md latest release": released.group(1) if released else "none",
}
if len(set(found.values())) != 1:
    print("contract-version: the three disagree: " + ", ".join(f"{k}={v}" for k, v in found.items()))
    sys.exit(1)
print(f"contract-version: ok (contract {tally.CONTRACT_VERSION})")
PY

cat > gates/error_codes.py <<'PY'
"""Gate: every error code the package raises is defined in tally.errors.CODES and documented in
docs/specs/contract/errors.md, and every documented code is defined."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tally.errors import CODES

RAISED = re.compile(r"TallyError\(\s*\"(E\d{3})\"")
raised = set()
for module in sorted((ROOT / "tally").glob("*.py")):
    raised.update(RAISED.findall(module.read_text(encoding="utf-8")))
table = (ROOT / "docs/specs/contract/errors.md").read_text(encoding="utf-8")
documented = set(re.findall(r"^\| (E\d{3}) \|", table, re.MULTILINE))
problems = [f"{code} is raised but not defined in CODES" for code in sorted(raised - set(CODES))]
problems += [f"{code} is raised but not documented" for code in sorted(raised - documented)]
problems += [f"{code} is documented but not defined" for code in sorted(documented - set(CODES))]
problems += [f"{code} is defined but not documented" for code in sorted(set(CODES) - documented)]
for problem in problems:
    print(f"error-codes: {problem}")
if problems:
    sys.exit(1)
print(f"error-codes: ok ({len(CODES)} codes)")
PY

cat > gates/model_roundtrip.py <<'PY'
"""Gate: a row read into an entry and written back is the same row (tests/test_model.py)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
done = subprocess.run([sys.executable, "-B", "-m", "unittest", "-q", "tests.test_model"], cwd=ROOT)
if done.returncode != 0:
    print("model-roundtrip: tests.test_model failed")
    sys.exit(1)
print("model-roundtrip: ok")
PY

cat > gates/legacy_columns.py <<'PY'
"""Gate: the column list of the v1 format in docs/specs/legacy-v1-columns.md matches the columns
the reader accepts from a v1 file."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SPEC = ROOT / "docs/specs/legacy-v1-columns.md"
if not SPEC.exists():
    print("legacy-columns: no v1 column spec; nothing to compare")
    sys.exit(0)

from tally import readers

listed = tuple(re.findall(r"^- `(\w+)`", SPEC.read_text(encoding="utf-8"), re.MULTILINE))
accepted = getattr(readers, "V1_COLUMNS", ())
if listed != accepted:
    print(f"legacy-columns: the spec lists {listed}, the reader accepts {accepted}")
    sys.exit(1)
print("legacy-columns: ok")
PY

cat > gates/python_floor.py <<'PY'
"""Gate: the interpreter is at least the oldest Python the package supports."""

import sys

FLOOR = (3, 6)
if sys.version_info < FLOOR:
    print(f"python-floor: Python {sys.version.split()[0]} is older than {FLOOR[0]}.{FLOOR[1]}")
    sys.exit(1)
print(f"python-floor: ok (Python {sys.version.split()[0]})")
PY

cat > tools/syntax_check.py <<'PY'
"""Parse every Python file of the package, the gates and the tools: a syntax error fails here."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
problems = []
for folder in ("tally", "gates", "tools", "tests"):
    for path in sorted((ROOT / folder).rglob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), str(path))
        except SyntaxError as error:
            problems.append(f"{path.relative_to(ROOT)}:{error.lineno}: {error.msg}")
print("\n".join(problems) if problems else "syntax: ok")
sys.exit(1 if problems else 0)
PY

cat > tools/docs_check.py <<'PY'
"""The documentation check: every relative link in README.md and docs/ resolves, and docs/cli.md
has a section for each command with each of its long options."""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tally.cli import build_parser

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
SECTION = re.compile(r"^## `tally (\w+)`\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def broken_links():
    problems = []
    for doc in sorted([ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]):
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            if "://" not in target and not (doc.parent / target).exists():
                problems.append(f"{doc.relative_to(ROOT)}: the link {target} leads nowhere")
    return problems


def undocumented():
    sections = dict(SECTION.findall((ROOT / "docs/cli.md").read_text(encoding="utf-8")))
    parser = build_parser()
    commands = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    problems = []
    for name, command in commands.choices.items():
        if name not in sections:
            problems.append(f"docs/cli.md: no section for `tally {name}`")
            continue
        for action in command._actions:
            for option in action.option_strings:
                if option.startswith("--") and option != "--help" and option not in sections[name]:
                    problems.append(f"docs/cli.md: `tally {name}` does not document {option}")
    problems += [f"docs/cli.md: `tally {name}` is not a command" for name in sections if name not in commands.choices]
    return problems


problems = broken_links() + undocumented()
print("\n".join(problems) if problems else "docs: ok")
sys.exit(1 if problems else 0)
PY

python3 - <<'PY'
from pathlib import Path

# A recipe line starts with a tab: written here with four spaces, then turned into one.
text = """PYTHON ?= python3
GATES = gates/contract_version.py gates/error_codes.py gates/model_roundtrip.py \\
        gates/legacy_columns.py gates/python_floor.py

.PHONY: check lint test test-unit test-integration gates docs-check

lint:
    $(PYTHON) -B tools/syntax_check.py

test-unit:
    $(PYTHON) -B -m unittest discover -s tests -t .

test-integration:
    $(PYTHON) -B tests/integration/run_suite.py

test: test-unit test-integration

gates:
    @for gate in $(GATES); do echo "gate $$gate"; $(PYTHON) -B $$gate || exit 1; done

docs-check:
    $(PYTHON) -B tools/docs_check.py

check: lint test-unit gates docs-check
"""
lines = ["\t" + line[4:] if line.startswith("    ") else line for line in text.splitlines()]
Path("Makefile").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

cat > .gitignore <<'TXT'
__pycache__/
*.pyc
/scratch/
/reports/
/.worktrees/
/build/
/dist/
*.tmp
TXT

cat > pyproject.toml <<'TOML'
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "tally"
version = "3.2.0"
description = "Read time entries and report on them."
requires-python = ">=3.8"
license = { text = "MIT" }

[project.scripts]
tally = "tally.cli:main"

[tool.setuptools]
packages = ["tally"]
TOML

cat > .github/workflows/ci.yml <<'YML'
name: ci
on:
  push:
  pull_request:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: make check
      - run: make test
YML

cat > README.md <<'MD'
# tally

Read time entries (CSV or JSON Lines) and report on them.

```sh
python3 -m tally report entries.csv --by week
python3 -m tally validate entries.csv --output json
python3 -m tally merge q1.csv q2.csv --out year.csv
```

- [Command reference](docs/cli.md)
- [Architecture](docs/architecture.md)
- [The public contract](docs/specs/contract/design.md) and its [error codes](docs/specs/contract/errors.md)
- [Output decisions](docs/specs/output/decisions.md)
- [Proof gates](docs/gates.md)
- [Changelog](CHANGELOG.md)
MD

cat > docs/cli.md <<'MD'
# Command reference

Every command reads CSV files (a header with `day,project,person,minutes,note`; `note` may be
left out) or JSON Lines files (`.jsonl`, one object per line with the same keys). Exit status: 0
done, 1 `validate` found problems, 2 an error ([error codes](specs/contract/errors.md)).

## `tally report`

`tally report FILE... [--by project|person|week|day]`

Totals the entries of every FILE by the grouping (`--by`, default `project`): a line for each
key with its entries and hours (`h:mm`), then the total.

## `tally validate`

`tally validate FILE... [--output text|json]`

Lists every problem in every FILE, where the other commands stop at the first. `--output json`
prints one object: `file_count`, `entry_count`, `problem_count` and `problems`.

## `tally merge`

`tally merge FILE... --out OUT`

Writes every distinct entry of the FILEs to OUT, sorted by day, project and person, and says
how many exact duplicates it dropped.

## `tally version`

`tally version`

Prints the version and the contract version.
MD

cat > docs/gates.md <<'MD'
# Proof gates

A proof gate is a small script that holds one property of the contract which no unit test
holds. `make gates` runs them all, and `make check` runs `make gates`.

| Gate | Holds |
| --- | --- |
| [contract_version.py](../gates/contract_version.py) | the contract version agrees in the code, the contract document and the changelog |
| [error_codes.py](../gates/error_codes.py) | every raised error code is defined and documented, and every documented code is defined |
| [model_roundtrip.py](../gates/model_roundtrip.py) | a row read and written back is the same row |
| [legacy_columns.py](../gates/legacy_columns.py) | the v1 column spec matches the columns the reader accepts from a v1 file |
| [python_floor.py](../gates/python_floor.py) | the interpreter is at least the oldest Python the package supports |
MD

cat > docs/specs/contract/design.md <<'MD'
# The public contract

Contract version: 3

What programs and people outside this repository rely on. Adding a command, an option or an
output field is not a new contract version; removing or renaming one, or changing what one
means, is: bump `CONTRACT_VERSION` in `tally/__init__.py`, and name the contract in the
changelog's release heading.

## Input

CSV with the header `day,project,person,minutes,note` (`note` may be left out), or JSON Lines
(`.jsonl`) with the same keys. `day` is `YYYY-MM-DD`; `project` and `person` are lower-case
letters, digits and dashes; `minutes` is a whole number from 1 to 1440.

## Commands

- `tally report FILE... [--by project|person|week|day]`
- `tally validate FILE... [--output text|json]`
- `tally merge FILE... --out OUT`
- `tally version`

## Output

Text output is for people and may change between minor versions. Machine output
(`--output json`) follows [the output decisions](../output/decisions.md) and changes only with
the contract.

## Exit status

0 done; 1 `validate` found problems; 2 an error, with a code from [errors.md](errors.md).
MD

cat > docs/specs/contract/errors.md <<'MD'
# Error codes

| Code | Meaning | Field |
| --- | --- | --- |
| E101 | an input file cannot be read | none |
| E102 | a value in an entry is invalid | the column of the value |
| E103 | an input file lacks a required column | the missing column |
| E104 | an option has an invalid value | the option |
MD

cat > docs/specs/output/decisions.md <<'MD'
# Output decisions

Decisions about what the command line prints. Each stands until a later entry replaces it.

## D-01 Durations in text output (2026-03-02)

Text output shows a duration as hours and minutes, `h:mm` (`12:05`), never as decimal hours:
people read it, and `12.08` hours reads as twelve hours and eight minutes.

## D-02 Dates (2026-03-02)

Every date the command line reads or prints is ISO 8601: a day is `YYYY-MM-DD`, a week is the
ISO week `YYYY-Www` (`2026-W14`).

## D-03 Field names in machine output (2026-05-19)

Machine output (`--output json`) is read by programs, so its names and units never change
under them:

- field names are lower-case snake_case: `entry_count`, never `entryCount` or `Entries`;
- a duration is whole minutes, an integer, in a field whose name ends in `_minutes`
  (`total_minutes`): never hours, never a float;
- a count is an integer in a field whose name ends in `_count`;
- a group's key is a field named after the grouping: `project`, `person`, `week` or `day`;
- a total is a field of the enclosing object (`total_minutes`), never a row with a made-up key
  such as `total`.

Rejected: decimal hours (readers round them differently); camelCase (the dashboards that read
this output are written in Python).

## D-04 Errors (2026-05-19)

An error is a failure to do the job: an unreadable file, an invalid entry in a file a command
reads, an invalid option value. Errors go to stderr, never stdout, and the exit status is 2.

- In text output, one line per error: `error[CODE] SOURCE:LINE: FIELD: MESSAGE`, leaving out
  the parts that do not apply.
- In machine output, one JSON object per line:
  `{"error": {"code": ..., "source": ..., "line": ..., "field": ..., "message": ...}}`, with
  every key present (`line` 0 and `field` "" where they do not apply); stdout stays empty.

`tally.errors.format_text` and `tally.errors.format_json` write the two forms. A finding of
`tally validate` is its output, not an error: it goes to stdout, and the exit status is 1.

Rejected: an error inside the JSON document on stdout (a reader would have to tell a report
from a failure by its shape).
MD

cat > docs/specs/legacy-v1-columns.md <<'MD'
# The v1 column set

Until contract 3, files carried hours rather than minutes. The v1 columns, in order:

- `date`
- `project`
- `who`
- `hours`
MD

cat > tickets/012-validate-json.md <<'MD'
# 012 validate: machine output

status: done

The nightly job reads what `validate` finds. Give it `--output json`.

## Acceptance

- [x] `tally validate --output json` prints one object with the counts and the problems
- [x] an unreadable file is an error in the machine form (D-04)
- [x] unit tests; docs/cli.md; a changelog line
MD

cat > tickets/013-merge-dedupe.md <<'MD'
# 013 merge: drop exact duplicates

status: done

Quarterly exports overlap at their edges, so a year merged from them counts some days twice.

## Acceptance

- [x] `tally merge` keeps one of each set of identical entries and says how many it dropped
- [x] unit tests; docs/cli.md; a changelog line
MD

cat > tickets/014-report-since.md <<'MD'
# 014 report: --since and --until

status: open

People ask for the report over a date range, and the dashboards for the last four weeks.

## Acceptance

- [ ] `tally report --since DAY --until DAY` keeps the entries from DAY to DAY, both included
- [ ] either option works alone; a range that ends before it starts is error E104
- [ ] unit tests for the filter and for the options
- [ ] docs/cli.md and docs/specs/contract/design.md list both options
- [ ] a changelog line under Unreleased
MD

cat > tickets/015-report-json.md <<'MD'
# 015 report: machine output

status: open

The dashboards read the report. Give `tally report` an `--output json` option; text stays the
default. Machine output follows docs/specs/output/decisions.md.
MD

cat > docs/architecture.md <<'MD'
# Architecture

One package, `tally/`, in layers that each import only the ones below them:

| Module | Does |
| --- | --- |
| `errors.py` | `TallyError`, the error codes, and the text and machine forms of an error |
| `model.py` | `Entry`, and turning a row of an input file into one |
| `readers.py` | rows from CSV and JSON Lines files, entries from rows, entries back to CSV |
| `aggregate.py` | grouping entries by project, person, ISO week or day |
| `report.py`, `validate.py`, `merge.py` | one module a command, on entries |
| `cli.py` | the parser, one `run_<command>` a command, and where errors are written |

An input problem is a `TallyError` raised where it is found, with the file and line, and caught
once, in `cli.py`, which writes it in the form the command's output asks for (decision D-04 in
[the output decisions](specs/output/decisions.md)). Nothing below `cli.py` prints.

Entries are frozen dataclasses, so a set of them drops exact duplicates (`merge.py`) and a list
of them sorts by day, project and person.

## Tests

`tests/` holds one unit-test module a module, plus `test_cli.py`, which runs the command line
in-process. `tests/integration/run_suite.py` runs the real command line on a generated year of
entries, waiting for the dashboard importer's poll after each stage, as the nightly job does.

## Gates

`gates/` holds the [proof gates](gates.md): properties of the contract that no unit test holds.
MD

cat > tickets/010-jsonl-input.md <<'MD'
# 010 read JSON Lines

status: done

One of the time trackers exports JSON Lines. Read `.jsonl` files beside CSV.

## Acceptance

- [x] a `.jsonl` file is read with the same keys as the CSV columns
- [x] a line that is not an object is E102 with its line number
- [x] unit tests; docs/cli.md
MD

cat > tickets/011-iso-weeks.md <<'MD'
# 011 report: ISO weeks

status: done

`--by week` put the first days of January in the last week of the year before.

## Acceptance

- [x] weeks are ISO weeks, `YYYY-Www`, at both edges of the year (D-02)
- [x] unit tests at the edges
MD

cat > CHANGELOG.md <<'MD'
# Changelog

## Unreleased

## 3.2.0 — 2026-08-14 (contract 3)

- validate: `--output json` (ticket 012)
- merge: exact duplicates are dropped and counted (ticket 013)
- the integration suite runs in CI

## 3.1.0 — 2026-07-07 (contract 3)

- Python 3.10 or later is required
- report: `--by week` uses ISO weeks at the edge of the year

## 3.0.0 — 2026-06-30 (contract 3)

- breaking: files carry minutes, not hours; the v1 column set is gone

## 2.4.0 — 2026-03-20 (contract 2)

- error codes, and the error format of decision D-04

## 2.0.0 — 2026-02-10 (contract 2)

- first release of the package and its command line
MD

cat > AGENTS.md <<'NOTE'
# tally

A Python library and command line for time entries: `python3 -m tally --help`. Python 3.10 or
later, standard library only; no dependency is added without asking.

## Layout

- `tally/` the package; `tally/cli.py` the command line.
- `tests/` unit tests (unittest); `tests/integration/` the integration suite.
- `gates/` proof gates: small scripts that each hold one property of the contract
  (`docs/gates.md` says which).
- `docs/cli.md` the command reference; `docs/specs/` the public contract and the recorded output
  decisions (`docs/specs/output/decisions.md`). Read them before you change any output.
- `tickets/` one file a ticket.
- `reports/` benchmark reports we compare across releases. Not in Git; keep it.
- `.worktrees/` where we put Git worktrees; `scratch/` and `*.tmp` are throwaway.

## Commands

- `make test-unit`: the unit tests, about 2 seconds.
- `make gates`: the proof gates, about 2 seconds.
- `make docs-check`: the links in the docs, and docs/cli.md against the parser; under a second.
- `make check`: syntax, unit tests, gates and docs-check; about 5 seconds. CI runs it.
- `make test-integration`: the integration suite, a generated year of entries through every
  command; about 75 seconds.
- `make test`: the unit tests, then the integration suite; about 80 seconds. CI runs it.

## House rules

- Output follows `docs/specs/output/decisions.md`; a new decision is recorded there.
- Removing or renaming anything in `docs/specs/contract/design.md` is a new contract version:
  bump `CONTRACT_VERSION` and name it in the changelog.
- A user-visible change gets a line under "Unreleased" in `CHANGELOG.md`.
- Commit messages read `area: what changed`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
