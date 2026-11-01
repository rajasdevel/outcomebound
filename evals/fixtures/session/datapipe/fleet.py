"""Generate distinct feed contracts, operator pages and executable examples."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


def generate() -> None:
    for number in range(1, 17):
        name = f"feed_{number:02}"
        table = "orders" if number % 2 else "events"
        key = "order_id" if table == "orders" else "event_id"
        columns = [
            {"name": key, "kind": "integer", "nullable": False},
            {"name": "received_at", "kind": "text", "nullable": False},
        ] + [
            {"name": f"attribute_{index}", "kind": kind, "nullable": index % 3 == 0}
            for index, kind in enumerate(("text", "integer", "real", "text", "text", "integer"), 1)
        ]
        old_columns = deepcopy(columns)
        old_key = [key]
        if number % 4 == 0:
            old_columns.pop()
            differences = []
        elif number % 4 == 1:
            old_columns[3]["kind"] = "text"
            differences = ["type changed for attribute_2"]
        elif number % 4 == 2:
            old_columns.append({"name": "legacy_code", "kind": "text", "nullable": True})
            differences = ["removed legacy_code"]
        else:
            old_key = ["received_at"]
            differences = ["primary key changed"]
        previous = {"tables": [{"name": table, "columns": old_columns, "key": old_key}]}
        value = {
            "source": name,
            "catalog": {"tables": [{"name": table, "columns": columns, "key": [key]}]},
            "previous_catalog": previous,
            "delivery": {
                "format": "csv",
                "encoding": "utf-8",
                "header": [column["name"] for column in columns],
                "checksum": "sha256",
                "count": "data records, excluding the header",
                "duplicate_keys": "literal cell identity within each extract",
                "empty_nullable": "accept",
                "empty_required": "reject",
            },
            "recovery": {
                "window_minutes": 60,
                "lateness_minutes": number * 5,
                "raw_days": 90,
                "archive_required": True,
                "checkpoint": "next unread source offset",
                "generation": "compare before advance",
                "window_start": "inclusive",
                "window_end": "inclusive",
                "cursor": "highest observed source offset plus one",
            },
            "checks": {
                "schema": "catalog comparison before loading",
                "files": "preflight before warehouse writes",
                "reconciliation": "all expected raw table counts",
                "checkpoint": "after load and reconciliation only",
                "stage": "deploy a committed revision, then smoke that revision",
                "prod": "read-only during diagnosis",
            },
        }
        path = Path(f"data/contracts/{name}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        path = Path(f"docs/feeds/{name}.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page(name, table, key, columns, number), encoding="utf-8")
        Path(f"tests/test_{name}.py").write_text(
            examples(name, key, number, differences), encoding="utf-8"
        )


def page(name: str, table: str, key: str, columns: list[dict], number: int) -> str:
    rows = "\n".join(
        f"| {col['name']} | {col['kind']} | {'yes' if col['nullable'] else 'no'} |"
        for col in columns
    )
    return f"""# {name} extract and recovery guide

This source supplies `{table}`. Its primary key is `{key}`. The contract is
`data/contracts/{name}.json`. Read it together with the catalog and recovery specs.
This is an example source contract, not the stage capacity profile.
Its previous catalog is stored beside the current catalog. Compare them before intake.
Record compatible changes and those that need a migration decision. Apply no migration
during this review. A schema result does not grant a retention change.

## Columns, in file order

| Column | Kind | Nullable |
| --- | --- | --- |
{rows}

## Intake

The CSV inspector reads one file at a time. It checks exact header order, required
fields, integer and real conversion, and repeated literal key cells. It returns the
data-row count and SHA256. It does not load a warehouse.

The manifest parser reads relative file names, table names, declared counts and checksums.
It does not inspect CSV content. The loader and reconciliation modules are separate callers.
The generated unit examples cover the existing inspector and checkpoint store.

## Recovery example

This source permits {number * 5} minutes of late arrivals. Recovery windows are 60 minutes.
The current planner records observed source offsets. It does not load a warehouse.
Checkpoint storage and plan construction are separate modules.
Use this source's catalog when inspecting its files; sources can have different schemas.

## Retention and archives

Keep raw data for 90 days. An archive is required before deletion.
An archive manifest must pass the same preflight checks as a current extract.
Count reconciliation is separate from file validation and from checkpoint storage.
An operator must check archive restore evidence before changing the recovery period.
Only the project owner can reduce the period or remove the archive requirement.
Holding that decision does not stop work on validation or replay.

## Current callers

The loader converts integer columns before inserting warehouse rows. The CSV inspector
checks file shape and field types without a warehouse connection. Catalog comparison
returns compatibility differences; it does not apply a migration. Checkpoint storage
uses a generation to reject stale writers. These modules have separate unit examples.
"""


def examples(name: str, key: str, number: int, differences: list[str]) -> str:
    return f'''"""Executable intake examples for {name}; no service or integration wait."""

import json
import tempfile
import unittest
from pathlib import Path

from datapipe.catalog import changes, parse
from datapipe.checkpoints import Checkpoint, Store
from datapipe.extract_io import inspect


class FeedExamples(unittest.TestCase):
    def setUp(self):
        document = json.loads(Path("data/contracts/{name}.json").read_text(encoding="utf-8"))
        self.table = next(iter(parse(document["catalog"]).values()))
        self.previous = next(iter(parse(document["previous_catalog"]).values()))
        self.header = ",".join(column.name for column in self.table.columns)
        self.row = "{number},2026-10-01T00:00:00Z,note,4,2.5,label,source,8"

    def test_inspection_counts_data_not_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "part.csv"
            path.write_text(self.header + "\\n" + self.row + "\\n", encoding="utf-8")
            self.assertEqual(inspect(path, self.table)["rows"], 1)

    def test_header_only_is_zero_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "part.csv"
            path.write_text(self.header + "\\n", encoding="utf-8")
            self.assertEqual(inspect(path, self.table)["rows"], 0)

    def test_reordered_header_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "part.csv"
            path.write_text(",".join(reversed(self.header.split(","))) + "\\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "header"):
                inspect(path, self.table)

    def test_bad_integer_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "part.csv"
            row = self.row.replace("note,4,", "note,broken,")
            path.write_text(self.header + "\\n" + row + "\\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "integer"):
                inspect(path, self.table)

    def test_duplicate_key_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "part.csv"
            path.write_text(self.header + "\\n" + (self.row + "\\n") * 2, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inspect(path, self.table)

    def test_same_schema_has_no_migration(self):
        self.assertEqual(changes(self.table, self.table), [])
        self.assertEqual(self.table.key, ("{key}",))

    def test_schema_transition_matches_recorded_example(self):
        self.assertEqual(changes(self.previous, self.table), {differences!r})

    def test_source_has_independent_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            self.assertEqual(store.read("{name}"), Checkpoint("{name}", 0, 0))
            self.assertEqual(
                store.advance("{name}", {number}, 0), Checkpoint("{name}", {number}, 1)
            )
            self.assertEqual(store.read("other"), Checkpoint("other", 0, 0))

    def test_stale_generation_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            store.advance("{name}", {number}, 0)
            with self.assertRaisesRegex(ValueError, "stale"):
                store.advance("{name}", {number + 1}, 0)
            self.assertEqual(store.read("{name}"), Checkpoint("{name}", {number}, 1))

'''
