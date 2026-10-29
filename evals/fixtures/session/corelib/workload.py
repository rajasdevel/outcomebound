"""Generate the library and compatibility material that the long tasks must use."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

write = runpy.run_path(str(Path(__file__).with_name("build.py")))["write"]


def modules():
    write(
        "tally/pipeline.py",
        '''
        """Compose selection, reconciliation and audit without changing caller data."""

        from dataclasses import dataclass
        from tally.aggregate import group
        from tally.audit import inspect
        from tally.reconcile import distinct, compare
        from tally.selection import Selection


        @dataclass(frozen=True)
        class Plan:
            by: str = "project"
            since: str | None = None
            until: str | None = None
            projects: frozenset = frozenset()
            people: frozenset = frozenset()
            unique: bool = False
            maximum: int = 480

            def selection(self):
                return Selection(self.since, self.until, self.projects, self.people)


        def prepare(entries, plan):
            selected = plan.selection().apply(entries)
            return distinct(selected) if plan.unique else selected


        def execute(entries, plan):
            selected = prepare(entries, plan)
            return group(selected, plan.by), inspect(selected, plan.maximum)


        def compare_selected(before, after, plan):
            return compare(prepare(before, plan), prepare(after, plan))
        ''',
    )
    write(
        "tally/batch.py",
        '''
        """One report for each named plan. Text is the released interface."""

        from tally.pipeline import execute
        from tally.report import render_text


        def run(entries, plans):
            entries = list(entries)
            return {name: render_text(execute(entries, plan)[0], plan.by)
                    for name, plan in sorted(plans.items())}
        ''',
    )
    write(
        "tally/catalog.py",
        '''
        """Read portable compatibility cases; expected output is recorded, not inferred."""

        import json
        from datetime import date
        from pathlib import Path
        from tally.model import Entry
        from tally.pipeline import Plan


        def load(path):
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            if document.get("version") != 1:
                raise ValueError("unknown catalog version")
            names = [case["name"] for case in document["cases"]]
            if len(names) != len(set(names)):
                raise ValueError("duplicate case name")
            return document["cases"]


        def entries(case):
            return [Entry(date.fromisoformat(row["day"]), row["project"], row["person"],
                          row["minutes"], row["note"]) for row in case["input"]]


        def plan(case):
            return Plan(**case["plan"])
        ''',
    )
    write(
        "tally/snapshot.py",
        '''
        """Build a read-only snapshot from a collection of plans."""

        from tally.audit import summary
        from tally.pipeline import execute


        def inspect(entries, plans):
            entries = list(entries)
            result = {}
            for name, plan in sorted(plans.items()):
                rows, findings = execute(entries, plan)
                result[name] = {
                    "keys": [row.key for row in rows],
                    "entry_count": sum(row.entry_count for row in rows),
                    "total_minutes": sum(row.minutes for row in rows),
                    "findings": summary(findings),
                }
            return result
        ''',
    )
    write(
        "tests/test_pipeline.py",
        """
        import unittest
        from datetime import date
        from tally.model import Entry
        from tally.pipeline import Plan, execute, compare_selected
        from tally.batch import run
        from tally.snapshot import inspect

        A = Entry(date(2026, 4, 1), "north", "worker", 30, "first")
        B = Entry(date(2026, 4, 2), "south", "worker", 45, "next")


        class PipelineTest(unittest.TestCase):
            def test_independent_plans_share_a_generator(self):
                result = run(iter([A, B]), {"all": Plan(), "south": Plan(projects={"south"})})
                self.assertIn("1:15", result["all"])
                self.assertIn("0:45", result["south"])

            def test_snapshot_counts_both_entries(self):
                self.assertEqual(inspect([A, B], {"all": Plan()})["all"], {
                    "keys": ["north", "south"], "entry_count": 2,
                    "total_minutes": 75, "findings": {}})

            def test_comparison_uses_selection(self):
                result = compare_selected([A], [A, B], Plan(projects={"south"}))
                self.assertEqual(result.summary(), {
                    "added_count": 1, "removed_count": 0, "common_count": 0,
                    "added_minutes": 45, "removed_minutes": 0})

            def test_execute_does_not_consume_twice(self):
                rows, findings = execute(iter([A, A]), Plan())
                self.assertEqual(rows[0].minutes, 60)
                self.assertEqual(findings[0].entry_count, 2)
        """,
    )


def catalog():
    cases: list[dict[str, object]] = []
    # Orthogonal examples have literal keys and totals, including ISO-year transitions.
    groups = {
        "project": [("2025-12-31", "north"), ("2026-01-05", "south")],
        "person": [("2025-12-31", "first"), ("2026-01-05", "second")],
        "day": [("2025-12-31", "2025-12-31"), ("2026-01-05", "2026-01-05")],
        "week": [("2025-12-31", "2026-W01"), ("2026-01-05", "2026-W02")],
    }
    for by, values in groups.items():
        for count in (0, 1, 2):
            for mode in ("ordinary", "duplicate", "note-change", "unique"):
                rows = []
                expected: list[dict[str, str | int]] = []
                for index, (day, key) in enumerate(values[:count]):
                    first = {
                        "day": day,
                        "project": ("north", "south")[index],
                        "person": ("first", "second")[index],
                        "minutes": (30, 45)[index],
                        "note": "work",
                    }
                    rows.append(first)
                    multiplier = 1
                    if mode in ("duplicate", "note-change", "unique"):
                        rows.append(
                            {**first, "note": "changed" if mode == "note-change" else "work"}
                        )
                        multiplier = 1 if mode == "unique" else 2
                    expected.append(
                        {
                            by: key,
                            "entry_count": multiplier,
                            "total_minutes": (30, 45)[index] * multiplier,
                        }
                    )
                cases.append(
                    {
                        "name": f"{by}-{count}-{mode}",
                        "input": list(reversed(rows)),
                        "plan": {"by": by, "unique": mode == "unique"},
                        "expected": {
                            "rows": expected,
                            "entry_count": sum(int(r["entry_count"]) for r in expected),
                            "total_minutes": sum(int(r["total_minutes"]) for r in expected),
                        },
                    }
                )
    # Filtered consumer examples have worked, literal rows, independent of the runtime grouping.
    truth = {
        "project": {
            "since": [("north", 1, 15), ("south", 1, 45)],
            "until": [("north", 1, 30), ("south", 1, 45)],
            "single": [("south", 1, 45)],
        },
        "person": {
            "since": [("first", 1, 15), ("second", 1, 45)],
            "until": [("first", 1, 30), ("second", 1, 45)],
            "single": [("second", 1, 45)],
        },
        "day": {
            "since": [("2026-01-05", 1, 45), ("2026-01-06", 1, 15)],
            "until": [("2025-12-31", 1, 30), ("2026-01-05", 1, 45)],
            "single": [("2026-01-05", 1, 45)],
        },
        "week": {
            "since": [("2026-W02", 2, 60)],
            "until": [("2026-W01", 1, 30), ("2026-W02", 1, 45)],
            "single": [("2026-W02", 1, 45)],
        },
    }
    for by, subset in {
        "project": [("north", 2, 45)],
        "person": [("first", 2, 45)],
        "day": [("2025-12-31", 1, 30), ("2026-01-06", 1, 15)],
        "week": [("2026-W01", 1, 30), ("2026-W02", 1, 15)],
    }.items():
        truth[by]["north"] = subset
        truth[by]["second"] = truth[by]["single"]
    limits: dict[str, dict[str, object]] = {
        "north": {"projects": ["north"]},
        "second": {"people": ["second"]},
        "since": {"since": "2026-01-05"},
        "until": {"until": "2026-01-05"},
        "single": {"since": "2026-01-05", "until": "2026-01-05"},
        "empty": {"since": "2026-01-07"},
    }
    entries = [
        {"day": "2025-12-31", "project": "north", "person": "first", "minutes": 30, "note": "work"},
        {"day": "2026-01-05", "project": "south", "person": "second", "minutes": 45, "note": ""},
        {"day": "2026-01-06", "project": "north", "person": "first", "minutes": 15, "note": "next"},
    ]
    for by, expectations in truth.items():
        for boundary, limit in limits.items():
            for mode in ("ordinary", "duplicate", "unique"):
                multiplier = 2 if mode == "duplicate" else 1
                expected = [
                    {
                        by: key,
                        "entry_count": count * multiplier,
                        "total_minutes": minutes * multiplier,
                    }
                    for key, count, minutes in expectations.get(boundary, [])
                ]
                cases.append(
                    {
                        "name": f"filtered-{by}-{boundary}-{mode}",
                        "input": entries if mode == "ordinary" else entries + entries,
                        "plan": {"by": by, "unique": mode == "unique", **limit},
                        "expected": {
                            "rows": expected,
                            "entry_count": sum(int(row["entry_count"]) for row in expected),
                            "total_minutes": sum(int(row["total_minutes"]) for row in expected),
                        },
                    }
                )
    write(
        "docs/compatibility/cases.json",
        json.dumps({"version": 1, "cases": cases}, indent=2) + "\n",
    )
    write(
        "docs/compatibility.md",
        """
        # Compatibility survey

        The [case catalog](compatibility/cases.json) records public examples.
        Compare new machine output with the recorded expected documents, not with another
        renderer. The empty examples must have an empty array and integer zero totals.
        Every grouping crosses an ISO-year boundary. Ordinary input order is deliberately reversed.
        Filtered examples cover upper, lower, one-day and empty ranges, with duplicate and
        unique plans. Their expected rows are worked values in the generator.
        The batch API must consume an input iterator only once across named plans.
        views.render shares that snapshot across reports, inspections and comparisons.
        A unique plan removes exact duplicates before counting. A changed note remains distinct.
        CLI input keeps duplicates. Batch plans can select and deduplicate before reporting.

        The expected documents describe counts, not a released report serialization API.
        Selection and note identity are library policy.
        """,
    )
    write(
        "docs/data-flow.md",
        """
        # Data flow

        The CLI reads entries and calls the report builder. The batch API shares one materialized
        input among named plans. A plan selects entries, optionally removes exact duplicates,
        groups them and audits the selected entries. Snapshot returns counts and audit findings.
        It is independent of report presentation. Compare selected exports before grouping:
        aggregation loses notes and cannot prove that two exports are identical.

        Do not turn report presentation into a retention policy. Bundle manifests prove content
        identity only. A list of candidates grants no authority to delete an export.
        The [library guide](library.md) and [compatibility survey](compatibility.md) describe
        supported composition. Historical decisions are under history/; they are evidence of
        old behaviour, not a replacement for current contracts.
        """,
    )


def history():
    decisions = [
        (
            "selection",
            "Both date bounds are inclusive.",
            "A one-day range keeps that day.",
            "Selection must keep input order and duplicates; sorting belongs to grouping.",
        ),
        (
            "identity",
            "Notes are part of entry identity.",
            "An empty note differs from work.",
            "Changed notes are removals and additions; totals alone do not prove equality.",
        ),
        (
            "machine-output",
            "All machine durations are integer minutes.",
            "Thirty minutes is 30.",
            "Text retains h:mm formatting. Machine consumers must never parse text tables.",
        ),
        (
            "batch",
            "Named plans share an input snapshot.",
            "A generator works for two plans.",
            "Return one value per sorted plan name. Never consume the source again.",
        ),
        (
            "retention",
            "Candidate lists never delete files.",
            "keep=0 lists every candidate.",
            "The maintainer must choose retention and verify backup before deletion.",
        ),
        (
            "release",
            "Package versions and contract versions are separate.",
            "3.3.0 keeps contract 3.",
            "An additive output option does not change the input contract or default renderer.",
        ),
        (
            "errors",
            "JSON failures go to stderr with exit 2.",
            "A missing file has code E101.",
            (
                "No partial report goes to stdout after an input error. "
                "Validation findings use exit 1."
            ),
        ),
        (
            "gates",
            "A gate needs a supported failure to reject.",
            "Contract 4 is rejected.",
            "Historical column proofs and Python floors can retire after their inputs change.",
        ),
    ]
    for number, (name, rule, example, caveat) in enumerate(decisions, 1):
        write(
            f"docs/history/{number:02d}-{name}.md",
            f"""
        # {name.replace("-", " ").title()}

        Current rule: {rule}
        Worked example: {example}

        {caveat}

        """,
        )


def main():
    modules()
    catalog()
    history()
    path = Path("docs/library.md")
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\nSee [data flow](data-flow.md) for batch and snapshot callers.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
