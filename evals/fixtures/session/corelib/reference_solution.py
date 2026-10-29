"""Literal regression cases and implementations for the model-free controls."""

from __future__ import annotations

SOURCE_TESTS = """
import json
import tempfile
import unittest
from pathlib import Path
from tally.inspection import reports, findings
from tally.sourcecache import clear

class InspectionTest(unittest.TestCase):
    def setUp(self):
        clear()
        self.addCleanup(clear)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps({"version":1,"plans":{"all":{}}}))

    def export(self, path, minutes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "day,project,person,minutes,note\\n2026-04-01,north,worker,"
            + str(minutes) + ",work\\n")

    def test_same_name_and_aliases(self):
        a, b = self.root / "east/export.csv", self.root / "west/export.csv"
        self.export(a, 30)
        self.export(b, 45)
        result = reports([a, b, a.parent / "../east/export.csv"], self.plan, output="json")
        self.assertEqual(result["all"]["total_minutes"], 75)
        self.assertEqual(findings([a, b], self.plan)["all"]["entry_count"], 2)
"""

FRESH_TESTS = """

    def test_current_bytes_win_over_path_size_and_mtime(self):
        import os
        from tally.errors import TallyError
        path = self.root / "current.csv"
        self.export(path, 30)
        stat = path.stat()
        self.assertEqual(reports([path], self.plan, output="json")["all"]["total_minutes"], 30)
        self.export(path, 45)
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(reports([path], self.plan, output="json")["all"]["total_minutes"], 45)
        self.assertEqual(findings([path], self.plan)["all"]["total_minutes"], 45)
        path.unlink()
        with self.assertRaises(TallyError) as caught:
            reports([path], self.plan, output="json")
        self.assertEqual(caught.exception.code, "E101")
"""

RESTRICTION_TESTS = """
import unittest
from datetime import date
from tally.model import Entry
from tally.selection import Selection
from tally.pipeline import Plan, execute, compare_selected
from tally.snapshot import inspect
from tally.planfiles import parse, describe

A = Entry(date(2026,4,2), "north", "worker", 30, "a")
B = Entry(date(2026,4,2), "south", "worker", 45, "b")

class RestrictionTest(unittest.TestCase):
    def test_exclusions_survive_composition_and_round_trip(self):
        original = Plan(by="day", unique=True, maximum=60)
        plan = original.restrict(Selection(projects=frozenset({"north", "south"}),
                                           excluded_projects=frozenset({"south"})))
        rows, findings = execute(iter([A,A,B]), plan)
        self.assertEqual([(row.key,row.minutes,row.entry_count) for row in rows],
                         [("2026-04-02",30,1)])
        self.assertEqual(inspect([A,A,B], {"one":plan})["one"]["total_minutes"], 30)
        self.assertEqual(plan.maximum, 60)
        self.assertEqual(original.selection().apply([A,B]), [A,B])
        empty = plan.restrict(Selection(excluded_projects=frozenset({"north"})))
        empty = empty.restrict(Selection())
        restored = parse(describe({"empty":empty}))["empty"]
        self.assertEqual(execute(iter([A,B]), restored)[0], [])
        self.assertFalse(compare_selected([A], [B], restored).changed)
        self.assertEqual(Plan().restrict(Selection()).selection().apply([A,B]), [A,B])

    def test_disjoint_names_remain_empty_in_a_portable_plan(self):
        plan = Plan(projects=frozenset({"north"})).restrict(
            Selection(projects=frozenset({"south"})))
        self.assertEqual(parse(describe({"one":plan}))["one"].selection().apply([A,B]), [])

    def test_person_exclusions_union_and_input_validation(self):
        a = Selection(excluded_people=frozenset({"worker"}))
        b = Selection(excluded_people=frozenset({"other"}))
        self.assertEqual(a.intersect(b).excluded_people, frozenset({"worker","other"}))
        self.assertEqual(a.intersect(b).apply([A,B]), [])
        for bad in ({"excluded_people":"worker"}, {"excluded_projects":[1]}, {"empty":1}):
            with self.assertRaises(ValueError):
                parse({"version":1,"plans":{"bad":bad}})
"""

NOTE_TESTS = """
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from datetime import date
from tally.model import Entry
from tally.reconcile import compare, distinct
from tally.comparison import review
from tally.pipeline import Plan
from tally.batch import run
from tally.snapshot import inspect
from tally.readers import write_csv, read

A = Entry(date(2026,4,2), "north", "worker", 30, "line one\\nline two")
B = replace(A, note="line one\\r\\nline two")
C = replace(A, note="line one line two")

class NoteLinesTest(unittest.TestCase):
    def test_all_identity_callers_agree_and_keep_original_values(self):
        self.assertEqual(distinct([B,A,C]), [B,C])
        self.assertFalse(review([A], [B], {"all":Plan()})["all"]["changed"])
        self.assertEqual(compare([A], [C]).apply([B,B]), [C])
        self.assertEqual(compare([A], [A]).apply([B]), [B])
        with self.assertRaises(ValueError):
            compare([A], []).apply([C])
        self.assertIn("1:00", run(iter([A,B,C]), {"one":Plan(unique=True)})["one"])
        self.assertEqual(inspect([A,B,C], {"one":Plan(unique=True)})["one"]["entry_count"], 2)
        self.assertEqual(B.note, "line one\\r\\nline two")

    def test_csv_preserves_embedded_note_newlines(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.csv"
            write_csv([A], path)
            self.assertEqual(read(path), [A])
"""


def restriction_revision(ref):
    ref.replace(
        "tally/selection.py",
        "    empty: bool = False",
        (
            "    empty: bool = False\n    excluded_projects: frozenset = frozen"
            "set()\n    excluded_people: frozenset = frozenset()"
        ),
    )
    ref.replace(
        "tally/selection.py",
        "projects, people, empty=empty)",
        (
            "projects, people, empty=empty,\n                         excluded_"
            "projects=self.excluded_projects | other.excluded_projects,\n      "
            "                   excluded_people=self.excluded_people | other.e"
            "xcluded_people)"
        ),
    )
    ref.replace(
        "tally/selection.py",
        "        if self.empty:",
        (
            "        if entry.project in self.excluded_projects or entry.perso"
            "n in self.excluded_people:\n            return False\n        if se"
            "lf.empty:"
        ),
    )
    ref.replace(
        "tally/pipeline.py",
        "from dataclasses import dataclass",
        "from dataclasses import dataclass, replace",
    )
    ref.replace(
        "tally/pipeline.py",
        "    maximum: int = 480",
        (
            "    maximum: int = 480\n    empty: bool = False\n    excluded_proje"
            "cts: frozenset = frozenset()\n    excluded_people: frozenset = fro"
            "zenset()"
        ),
    )
    ref.replace(
        "tally/pipeline.py",
        "        return Selection(self.since, self.until, self.projects, self.people)",
        """        return Selection(self.since, self.until, self.projects, self.people,
                         empty=self.empty, excluded_projects=self.excluded_projects,
                         excluded_people=self.excluded_people)

    def restrict(self, selection):
        chosen = self.selection().intersect(selection)
        return replace(self, since=chosen.since.isoformat() if chosen.since else None,
                       until=chosen.until.isoformat() if chosen.until else None,
                       projects=chosen.projects, people=chosen.people, empty=chosen.empty,
                       excluded_projects=chosen.excluded_projects,
                       excluded_people=chosen.excluded_people)""",
    )
    ref.replace(
        "tally/planfiles.py",
        '"unique", "maximum"}',
        '"unique", "maximum", "empty", "excluded_projects", "excluded_people"}',
    )
    ref.replace(
        "tally/planfiles.py",
        'for field in ("projects", "people"):',
        'for field in ("projects", "people", "excluded_projects", "excluded_people"):',
    )
    ref.replace(
        "tally/planfiles.py",
        "        plan = Plan(**value)",
        (
            '        if type(value.get("empty", False)) is not bool:\n         '
            '   raise ValueError("empty must be boolean")\n        plan = Plan('
            "**value)"
        ),
    )
    ref.replace(
        "tally/planfiles.py",
        '"unique": plan.unique, "maximum": plan.maximum}',
        (
            '"unique": plan.unique, "maximum": plan.maximum, "empty":plan.empt'
            'y,\n               "excluded_projects":sorted(plan.excluded_projec'
            'ts), "excluded_people":sorted(plan.excluded_people)}'
        ),
    )
    ref.write("tests/test_restrictions.py", RESTRICTION_TESTS)
    for name in ("docs/library.md", "docs/consumers/plans.md"):
        ref.write(
            name,
            (ref.root / name).read_text(encoding="utf-8")
            + (
                "\nPlan.restrict preserves an empty intersection and unions project"
                " and person exclusions. Portable plans include empty and both exc"
                "lusion lists.\n"
            ),
        )
    ref.run(
        "python3",
        "-B",
        "-m",
        "unittest",
        "tests.test_restrictions",
        "tests.test_selection",
        "tests.test_pipeline",
        "tests.test_consumers",
    )


def identity_revision(ref):
    ref.replace(
        "tally/reconcile.py",
        "entry.minutes, entry.note",
        'entry.minutes, entry.note.replace("\\r\\n", "\\n")',
    )
    ref.replace("tally/readers.py", "import csv", "import csv\nimport io")
    ref.replace(
        "tally/readers.py",
        "csv.DictReader(text.splitlines())",
        'csv.DictReader(io.StringIO(text, newline=""))',
    )
    ref.write("tests/test_note_lines.py", NOTE_TESTS)
    ref.write(
        "docs/library.md",
        (ref.root / "docs/library.md").read_text(encoding="utf-8")
        + (
            "\nIdentity treats CRLF and LF inside notes as equal; other whitesp"
            "ace and original entry values are preserved. CSV preserves embedd"
            "ed note newlines.\n"
        ),
    )
    ref.run(
        "python3",
        "-B",
        "-m",
        "unittest",
        "tests.test_note_lines",
        "tests.test_reconcile",
        "tests.test_pipeline",
        "tests.test_consumers",
    )


EXPORT_CODE = '''
"""Write an inspected report bundle without replacing an existing destination."""

import json
import re
import tempfile
from pathlib import Path
from tally.batch import run
from tally.bundles import manifest
from tally.planfiles import load
from tally.sourcecache import collect

NAME = re.compile(r"[a-z][a-z0-9_-]*")


def export(paths, plan_path, destination, output="text"):
    if output not in {"text", "json"}:
        raise ValueError("unsupported output")
    plans = load(plan_path)
    if any(not NAME.fullmatch(name) or name == "manifest" for name in plans):
        raise ValueError("unsafe export name")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("destination exists")
    entries = collect(paths)
    values = run(entries, plans, output=output)
    with tempfile.TemporaryDirectory(prefix=".tally-export-", dir=destination.parent) as folder:
        temporary = Path(folder) / "bundle"
        temporary.mkdir()
        names = []
        for name, value in sorted(values.items()):
            member = name + (".json" if output == "json" else ".txt")
            text = json.dumps(value, sort_keys=True) + "\\n" if output == "json" else value
            (temporary / member).write_text(text, encoding="utf-8")
            names.append(member)
        record = manifest(temporary, names)
        (temporary / "manifest.json").write_text(
            json.dumps(record, sort_keys=True) + "\\n", encoding="utf-8")
        temporary.rename(destination)
    return record
'''

EXPORT_TESTS = """
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tally.inspection import export
from tally.bundles import verify
from tally.errors import TallyError
from tally.sourcecache import clear

class ExportTest(unittest.TestCase):
    def setUp(self):
        clear()
        self.addCleanup(clear)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.data = self.root / "input.csv"
        self.data.write_text("day,project,person,minutes,note\\n"
                             "2026-04-01,north,worker,30,first\\n"
                             "2026-04-02,south,worker,45,next\\n", encoding="utf-8")
        self.plan = self.root / "plans.json"
        self.plans({"all":{}, "north":{"projects":["north"]}})

    def plans(self, value):
        self.plan.write_text(json.dumps({"version":1,"plans":value}), encoding="utf-8")

    def test_json_and_text_members_and_verifiable_manifest(self):
        target = self.root / "json"
        record = export(iter([self.data]), self.plan, target, output="json")
        self.assertEqual([row["name"] for row in record["files"]], ["all.json","north.json"])
        self.assertEqual(json.loads((target / "all.json").read_text(encoding="utf-8"))[
            "total_minutes"], 75)
        self.assertEqual(verify(target, record), [])
        self.assertEqual(json.loads(
            (target / "manifest.json").read_text(encoding="utf-8")), record)
        export([self.data], self.plan, self.root / "text")
        self.assertIn("0:30", (self.root / "text/north.txt").read_text(encoding="utf-8"))

    def test_bad_names_and_output_are_refused_before_reading_sources(self):
        class Unreadable:
            def __iter__(self):
                raise AssertionError("source read before validation")
        for name in ("../escape", "/absolute", "manifest", "bad/name"):
            self.plans({name:{}})
            with self.assertRaisesRegex(ValueError,"unsafe export name"):
                export(Unreadable(), self.plan, self.root / "output")
        with self.assertRaisesRegex(ValueError,"unsupported output"):
            export(Unreadable(), self.plan, self.root / "output", output="xml")
        self.assertFalse((self.root / "output").exists())

    def test_failure_leaves_no_partial_bundle_and_existing_data_is_preserved(self):
        target = self.root / "output"
        with self.assertRaises(TallyError):
            export([self.root / "absent.csv"], self.plan, target)
        self.assertFalse(target.exists())
        original = Path.write_text
        def fail_member(path, text, **kwargs):
            if path.name == "north.json":
                raise OSError("synthetic disk failure")
            return original(path, text, **kwargs)
        with patch.object(Path, "write_text", fail_member):
            with self.assertRaisesRegex(OSError,"synthetic disk failure"):
                export([self.data], self.plan, target, output="json")
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob(".tally-export-*")), [])
        target.mkdir()
        (target / "keep").write_text("original", encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"destination exists"):
            export([self.data], self.plan, target)
        self.assertEqual((target / "keep").read_text(encoding="utf-8"), "original")
"""


def export_bundle(ref):
    ref.write("tally/exporting.py", EXPORT_CODE)
    path = ref.root / "tally/inspection.py"
    ref.write(
        "tally/inspection.py",
        path.read_text(encoding="utf-8")
        + """


def export(paths, plan_path, destination, output="text"):
    from tally.exporting import export as write_bundle
    return write_bundle(paths, plan_path, destination, output=output)
""",
    )
    ref.write("tests/test_exporting.py", EXPORT_TESTS)
    ref.write(
        "docs/consumers/exports.md",
        "# Report bundles\n\ninspection.export accepts source paths, a plan file, "
        "a new destination "
        "and text or JSON output. It validates safe plan names before reading sources. "
        "It writes one sorted member per plan and a manifest that bundles.verify can check. "
        "A failed read or write leaves no destination. An existing destination is preserved.\n",
    )
    ref.run("python3", "-B", "-m", "unittest", "tests.test_exporting")
