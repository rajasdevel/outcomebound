"""Install a read-only view coordinator and tests that use the report and snapshot callers."""

import runpy
from pathlib import Path

write = runpy.run_path(str(Path(__file__).with_name("build.py")))["write"]

write(
    "tally/views.py",
    '''
"""Render named views from one source snapshot after validating the whole request."""

from tally.planfiles import parse
from tally.batch import run
from tally.snapshot import inspect
from tally.comparison import review


def prepare(document):
    if not isinstance(document, dict) or set(document) != {"plans", "views"}:
        raise ValueError("expected plans and views")
    plans = parse(document["plans"])
    views = document["views"]
    if not isinstance(views, dict) or not views:
        raise ValueError("expected named views")
    result = {}
    for name, view in sorted(views.items()):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("view name is empty")
        if not isinstance(view, dict) or set(view) != {"plan", "kind"}:
            raise ValueError("unknown view field")
        if view["plan"] not in plans:
            raise ValueError("view names an unknown plan")
        if view["kind"] not in {"report", "snapshot", "comparison"}:
            raise ValueError("unknown view kind")
        result[name] = (view["plan"], view["kind"])
    return plans, result


def render(entries, document, output="text", before=None):
    plans, views = prepare(document)
    if output not in {"text", "json"}:
        raise ValueError("unsupported report output")
    needed = {kind for _, kind in views.values()}
    if "comparison" in needed and before is None:
        raise ValueError("comparison requires a baseline")
    entries = list(entries)
    values = {}
    if "report" in needed:
        values["report"] = (run(entries, plans) if output == "text"
                            else run(entries, plans, output=output))
    if "snapshot" in needed:
        values["snapshot"] = inspect(entries, plans)
    if "comparison" in needed:
        values["comparison"] = review(before, entries, plans)
    return {name: values[kind][plan] for name, (plan, kind) in views.items()}
''',
)

write(
    "tests/test_views.py",
    """
import unittest
from copy import deepcopy
from datetime import date
from tally.model import Entry
from tally.views import prepare, render

A = Entry(date(2026, 4, 1), "north", "worker", 30, "first")
B = Entry(date(2026, 4, 2), "south", "worker", 45, "next")


def request():
    return {"plans": {"version": 1, "plans": {"all": {}, "north": {"projects": ["north"]}}},
            "views": {"table": {"plan": "all", "kind": "report"},
                      "counts": {"plan": "north", "kind": "snapshot"}}}


class ViewsTest(unittest.TestCase):
    def test_one_shot_source_is_shared_across_report_and_snapshot(self):
        result = render(iter([A, B]), request())
        self.assertIn("1:15", result["table"])
        self.assertEqual(result["counts"], {"keys": ["north"], "entry_count": 1,
                                           "total_minutes": 30, "findings": {}})

    def test_comparison_materializes_baseline_only_once(self):
        document = request()
        document["views"] = {"a": {"plan": "all", "kind": "comparison"},
                             "b": {"plan": "north", "kind": "comparison"}}
        result = render(iter([A, B]), document, before=iter([A]))
        self.assertEqual(result["a"]["summary"], {"added_count": 1, "removed_count": 0,
            "common_count": 1, "added_minutes": 45, "removed_minutes": 0})
        self.assertFalse(result["b"]["changed"])

    def test_bad_view_is_refused_before_reading_any_entries(self):
        class Unreadable:
            def __iter__(self):
                raise AssertionError("source read before validation")
        for change in ({"plan": "missing", "kind": "report"},
                       {"plan": "all", "kind": "delete"},
                       {"plan": "all", "kind": "report", "unknown": True}):
            document = request()
            document["views"]["bad"] = change
            with self.subTest(change=change), self.assertRaises(ValueError):
                render(Unreadable(), document)

    def test_baseline_is_required_for_comparison(self):
        document = request()
        document["views"]["a"] = {"plan": "all", "kind": "comparison"}
        with self.assertRaisesRegex(ValueError, "baseline"):
            render([], document)

    def test_views_do_not_mutate_the_request_or_entries(self):
        document = request()
        original = deepcopy(document)
        render([A, B], document)
        self.assertEqual(document, original)
        self.assertEqual([A.minutes, B.minutes], [30, 45])

    def test_default_and_explicit_text_are_identical(self):
        self.assertEqual(render([A, B], request()), render([A, B], request(), output="text"))

    def test_unknown_output_is_refused(self):
        with self.assertRaisesRegex(ValueError, "output"):
            render([], request(), output="yaml")
""",
)
