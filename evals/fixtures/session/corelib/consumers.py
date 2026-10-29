"""Generate independent consumers whose contracts matter to the library work."""

from __future__ import annotations

import runpy
from pathlib import Path

write = runpy.run_path(str(Path(__file__).with_name("build.py")))["write"]


def main():
    write(
        "tally/planfiles.py",
        '''
        """Portable named plans. Parse before reading any exports."""

        import json
        from pathlib import Path
        from tally.aggregate import GROUPINGS
        from tally.pipeline import Plan

        FIELDS = {"by", "since", "until", "projects", "people", "unique", "maximum"}


        def parse(document):
            if not isinstance(document, dict) or document.get("version") != 1:
                raise ValueError("unknown plan format")
            plans = document.get("plans")
            if not isinstance(plans, dict) or not plans:
                raise ValueError("expected named plans")
            result = {}
            for name, value in sorted(plans.items()):
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("expected a nonempty plan name")
                if not isinstance(value, dict) or set(value) - FIELDS:
                    raise ValueError("unknown plan field")
                value = dict(value)
                if value.get("by", "project") not in GROUPINGS:
                    raise ValueError("unknown grouping")
                if type(value.get("unique", False)) is not bool:
                    raise ValueError("unique must be boolean")
                if type(value.get("maximum", 480)) is not int or value.get("maximum", 480) < 1:
                    raise ValueError("maximum must be a positive integer")
                for field in ("projects", "people"):
                    names = value.get(field, [])
                    if not isinstance(names, list) or any(not isinstance(v, str) for v in names):
                        raise ValueError("expected name list")
                    value[field] = frozenset(names)
                plan = Plan(**value)
                plan.selection()
                result[name] = plan
            return result


        def load(path):
            return parse(json.loads(Path(path).read_text(encoding="utf-8")))


        def describe(plans):
            return {"version": 1, "plans": {
                name: {"by": plan.by, "since": plan.since, "until": plan.until,
                       "projects": sorted(plan.projects), "people": sorted(plan.people),
                       "unique": plan.unique, "maximum": plan.maximum}
                for name, plan in sorted(plans.items())}}
        ''',
    )
    write(
        "tally/comparison.py",
        '''
        """Review two sets of exports under the same named plans."""

        from tally.pipeline import compare_selected, prepare
        from tally.reconcile import project_delta


        def review(before, after, plans):
            before, after = list(before), list(after)
            result = {}
            for name, plan in sorted(plans.items()):
                difference = compare_selected(before, after, plan)
                result[name] = {
                    "changed": difference.changed,
                    "summary": difference.summary(),
                    "project_minutes": project_delta(prepare(before, plan), prepare(after, plan)),
                }
            return result


        def unchanged(before, after, plans):
            return all(not item["changed"] for item in review(before, after, plans).values())
        ''',
    )
    write(
        "tally/inspection.py",
        '''
        """Inspection never writes an export or applies a retention rule."""

        from tally.readers import read
        from tally.batch import run
        from tally.snapshot import inspect
        from tally.planfiles import load


        def entries(paths):
            result = []
            for path in paths:
                result.extend(read(path))
            return result


        def reports(paths, plan_path):
            plans = load(plan_path)
            return run(entries(paths), plans)


        def findings(paths, plan_path):
            plans = load(plan_path)
            return inspect(entries(paths), plans)
        ''',
    )
    write(
        "tests/test_consumers.py",
        """
        import json
        import tempfile
        import unittest
        from datetime import date
        from pathlib import Path
        from tally.model import Entry
        from tally.pipeline import Plan
        from tally.planfiles import parse, describe, load
        from tally.comparison import review, unchanged
        from tally.inspection import reports, findings
        from tally.readers import write_csv

        A = Entry(date(2026, 4, 1), "north", "worker", 30, "first")
        B = Entry(date(2026, 4, 2), "south", "worker", 45, "next")


        class ConsumerTest(unittest.TestCase):
            def test_named_plans_round_trip(self):
                plans = {"all": Plan(), "one": Plan(projects=frozenset({"north"}), unique=True)}
                self.assertEqual(parse(describe(plans)), plans)

            def test_parse_does_not_change_input(self):
                document = {"version": 1, "plans": {"one": {"projects": ["north", "north"]}}}
                self.assertEqual(parse(document)["one"].projects, frozenset({"north"}))
                self.assertEqual(document["plans"]["one"]["projects"], ["north", "north"])

            def test_unknown_fields_are_refused(self):
                with self.assertRaisesRegex(ValueError, "unknown plan field"):
                    parse({"version": 1, "plans": {"one": {"retention": 0}}})

            def test_invalid_plan_fields(self):
                bad = [{"by": "month"}, {"maximum": 0}, {"maximum": True},
                       {"unique": 1}, {"projects": "north"}, {"people": [1]}]
                for value in bad:
                    with self.subTest(value=value), self.assertRaises(ValueError):
                        parse({"version": 1, "plans": {"one": value}})

            def test_comparison_conserves_minutes(self):
                result = review(iter([A]), iter([B]), {"all": Plan()})["all"]
                self.assertEqual(result, {"changed": True, "summary": {
                    "added_count": 1, "removed_count": 1, "common_count": 0,
                    "added_minutes": 45, "removed_minutes": 30},
                    "project_minutes": {"north": -30, "south": 45}})

            def test_unchanged_compares_entries(self):
                self.assertTrue(unchanged([A], [A], {"all": Plan()}))
                self.assertFalse(unchanged([A], [B], {"all": Plan()}))

            def test_independent_plans_consume_once(self):
                result = review(iter([A]), iter([A, B]), {
                    "all": Plan(), "one": Plan(projects=frozenset({"north"}))})
                self.assertEqual(result["all"]["summary"]["added_minutes"], 45)
                self.assertFalse(result["one"]["changed"])

            def test_inspection_reads_but_never_changes_exports(self):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    data, plan = root / "entries.csv", root / "plan.json"
                    write_csv([A, B], data)
                    plan.write_text(json.dumps({"version": 1, "plans": {
                        "all": {}, "north": {"projects": ["north"]}}}), encoding="utf-8")
                    before = data.read_bytes()
                    self.assertIn("1:15", reports([data], plan)["all"])
                    self.assertEqual(findings([data], plan)["north"]["total_minutes"], 30)
                    self.assertEqual(data.read_bytes(), before)
                    self.assertEqual(load(plan)["north"].projects, frozenset({"north"}))
        """,
    )
    guides = {
        "plans": (
            "A plan is a selection plus grouping and audit options.",
            "planfiles.parse checks the whole document before any export is read.",
            "planfiles.describe writes the supported fields in sorted name order.",
            "Both date bounds are inclusive. Empty name lists mean no restriction.",
            "A maximum is a positive integer. Booleans do not count as integers here.",
            "Unknown fields are errors; never infer a retention policy from a plan.",
        ),
        "comparisons": (
            "comparison.review materializes both input iterators once.",
            "Each named plan gets the same before and after entries.",
            "compare_selected applies selection before checking entry identity.",
            "A changed note changes identity even when minute totals do not change.",
            "Project deltas explain totals but do not prove entry equality.",
            "Compare files before deciding whether to replace them. No comparison deletes data.",
        ),
        "inspection": (
            "inspection.reports reads exports in the supplied path order.",
            "inspection.findings shares the plan contract with report generation.",
            "Snapshot counts and audit findings describe the selected input.",
            "The default report remains text. Machine output is an explicit report option.",
            "Inspection has no write capability, deployment step or retention setting.",
            "Keep a failed input intact until the operator has read its error and source.",
        ),
    }
    for name, rules in guides.items():
        body = f"# {name.title()}\n\n"
        for number, rule in enumerate(rules, 1):
            body += f"## Rule {number}\n\n{rule}\n\n"
        body += (
            "## Checks\n\nRun `python3 -B -m unittest tests.test_consumers tests.test_pipeline`.\n"
        )
        body += "Read the [data flow](../data-flow.md) before changing a shared library function.\n"
        write(f"docs/consumers/{name}.md", body)
    write(
        "docs/consumers/operations.md",
        """
        # Consumer recovery checklist

        | Symptom | First observation | Caller | Preserve |
        | --- | --- | --- | --- |
        | Final day absent | Check inclusive upper date | pipeline | original export |
        | Notes collapsed | Compare identities before grouping | comparison | both exports |
        | Named plan empty | Read plan name and filters | planfiles | plan document |
        | Second plan empty | Check one-shot iterator use | batch | first report |
        | Wrong weekly key | Check ISO year at boundary | aggregate | input dates |
        | New error key | Compare with error contract | CLI | stderr and exit status |
        | Missing snapshot finding | Inspect selected rows | snapshot | source entries |
        | Stale manifest | Verify member digest | bundles | retained CSV |

        The operator uses inspection for a read-only view. Inspection does not create a release,
        update an export, or remove cache files. The maintainer owns retention and deployment.
        Record the input path as a relative path in this project. Keep private data out of notes.

        A held policy decision stops deletion only. It does not stop selection or comparison
        fixes, safe cache removal, checks or recovery documentation. Leave the decision with
        its owner and next step. Keep drafts and their current Git state.

        When a session stops, use the progress record and reachable commits. Read-only inspection
        may come first, but no new work starts before the record is read. A completed ticket is
        not open merely because the new session lacks its conversation. Keep its commit.
        """,
    )


if __name__ == "__main__":
    main()
