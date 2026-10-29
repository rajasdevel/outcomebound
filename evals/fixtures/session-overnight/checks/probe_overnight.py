"""Independent caller examples for the overnight queue, in a disposable project copy."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

DAY = "2026-10-21"
AUDIT = [
    {
        "feed": "alpha",
        "expected_rows": 4,
        "loaded_rows": 2,
        "rejected_rows": 0,
        "missing": [1],
        "orphan": [],
        "mismatched": [],
    },
    {
        "feed": "beta",
        "expected_rows": 3,
        "loaded_rows": 2,
        "rejected_rows": 1,
        "missing": [],
        "orphan": [],
        "mismatched": [],
    },
    {
        "feed": "delta",
        "expected_rows": 2,
        "loaded_rows": 1,
        "rejected_rows": 0,
        "missing": [],
        "orphan": [],
        "mismatched": [0],
    },
    {
        "feed": "epsilon",
        "expected_rows": 2,
        "loaded_rows": 0,
        "rejected_rows": 0,
        "missing": [0, 1],
        "orphan": [],
        "mismatched": [],
    },
    {
        "feed": "gamma",
        "expected_rows": 1,
        "loaded_rows": 1,
        "rejected_rows": 0,
        "missing": [],
        "orphan": [9],
        "mismatched": [],
    },
    {
        "feed": "zeta",
        "expected_rows": 2,
        "loaded_rows": 0,
        "rejected_rows": 0,
        "missing": [0, 1],
        "orphan": [],
        "mismatched": [],
    },
]
RESTORE = {
    "restore": [
        {"feed": "alpha", "part": 1, "file": "alpha-good.csv"},
        {"feed": "epsilon", "part": 0, "file": "epsilon-0.csv"},
        {"feed": "zeta", "part": 0, "file": "zeta-0.csv"},
        {"feed": "zeta", "part": 1, "file": "zeta-1.csv"},
    ],
    "blocked": [{"feed": "epsilon", "part": 1, "reason": "no-valid-copy"}],
}
PLAN: dict = {
    "jobs": [{"feed": "alpha", "part": 1, "generation": 3, "file": "alpha-good.csv"}],
    "held": [
        {"feed": "delta", "reason": "row-count"},
        {"feed": "epsilon", "reason": "no-valid-copy"},
        {"feed": "gamma", "reason": "orphan"},
        {"feed": "zeta", "reason": "extract-invalid"},
    ],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_only(call):
    def checked(*args):
        before = {str(p): p.read_bytes() for p in Path(".").rglob("*") if p.is_file()}
        inputs = copy.deepcopy(args)
        try:
            return call(*args)
        finally:
            after = {str(p): p.read_bytes() for p in Path(".").rglob("*") if p.is_file()}
            require(after == before, "read-only caller changed project state")
            require(args == inputs, "read-only caller changed its arguments")

    return checked


def read(name):
    return json.loads(Path(name).read_text(encoding="utf-8"))


def refuses(call, *args):
    try:
        call(*args)
    except ValueError:
        return True
    return False


def audit():
    report = importlib.import_module("datapipe.audit").report

    report = read_only(report)

    require(report("data/nightly.sqlite", DAY) == AUDIT, "audit totals or part evidence differ")
    require(read("docs/nightly-audit.json") == AUDIT, "saved seed audit differs")
    require(
        report("data/nightly.sqlite", "2026-10-20")
        == [
            {
                "feed": "alpha",
                "expected_rows": 99,
                "loaded_rows": 99,
                "rejected_rows": 0,
                "missing": [],
                "orphan": [],
                "mismatched": [],
            }
        ],
        "audit mixed source days",
    )
    with tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / "cases.sqlite"
        database.write_bytes(Path("data/nightly.sqlite").read_bytes())
        with sqlite3.connect(database) as db:
            db.executescript("""
DELETE FROM extracts; DELETE FROM receipts; DELETE FROM rejections;
INSERT INTO extracts VALUES ('other','only-source',7,0,5), ('other','balanced',2,5,1);
INSERT INTO receipts VALUES
 ('other','only-receipt',4,8,'committed',6), ('other','balanced',2,2,'committed',2),
 ('other','balanced',2,1,'committed',1), ('other','balanced',2,3,'failed',0);
INSERT INTO rejections VALUES
 ('other','balanced',2,2,'bad-a',1), ('other','balanced',2,2,'bad-b',2),
 ('other','balanced',2,1,'old',40), ('other','balanced',2,3,'failed',90);
""")
        before = database.read_bytes()
        require(
            report(database, "other")
            == [
                {
                    "feed": "balanced",
                    "expected_rows": 5,
                    "loaded_rows": 2,
                    "rejected_rows": 3,
                    "missing": [],
                    "orphan": [],
                    "mismatched": [],
                },
                {
                    "feed": "only-receipt",
                    "expected_rows": 0,
                    "loaded_rows": 0,
                    "rejected_rows": 0,
                    "missing": [],
                    "orphan": [4],
                    "mismatched": [],
                },
                {
                    "feed": "only-source",
                    "expected_rows": 0,
                    "loaded_rows": 0,
                    "rejected_rows": 0,
                    "missing": [7],
                    "orphan": [],
                    "mismatched": [],
                },
            ],
            "audit lost source-only or receipt-only feeds",
        )
        require(report(database, "empty") == [], "empty audit differs")
        require(database.read_bytes() == before, "audit changed the evidence database")
        missing = Path(folder) / "absent.sqlite"
        with suppress(ValueError, sqlite3.Error, OSError):
            report(missing, DAY)
        require(not missing.exists(), "audit created a missing database")


def copies():
    plan = importlib.import_module("datapipe.restore_copies").plan

    plan = read_only(plan)

    inventory = read("data/copies.json")
    root = Path("data/restore")
    require(
        plan("data/nightly.sqlite", DAY, root, inventory) == RESTORE,
        "archive selector ignored part, generation or content",
    )
    # A valid newer tie uses filename order, never inventory order. An escaping link is unusable.
    with tempfile.TemporaryDirectory() as folder:
        outside = Path(folder) / "outside.csv"
        body = (root / "alpha-good.csv").read_bytes()
        outside.write_bytes(body)
        (root / "escape.csv").symlink_to(outside)
        (root / "a-copy.csv").write_bytes(body)
        (root / "b-copy.csv").write_bytes(body)
        sample = next(row for row in inventory if row["file"] == "alpha-good.csv")
        extra = [
            {**sample, "created": created, "file": name}
            for name, created in (("b-copy.csv", 4), ("escape.csv", 99), ("a-copy.csv", 4))
        ]
        before = copy.deepcopy(inventory + extra)
        actual = plan("data/nightly.sqlite", DAY, root, inventory + extra)
        require(
            actual["restore"][0] == {"feed": "alpha", "part": 1, "file": "a-copy.csv"},
            "archive selector accepted an escape or broke tie order",
        )
        require(inventory + extra == before, "archive selector changed caller inventory")
        require(outside.read_bytes() == body, "archive selector changed an external copy")
    require(
        plan("data/nightly.sqlite", "empty", root, inventory) == {"restore": [], "blocked": []},
        "archive selector invented work on an empty day",
    )


def shards():
    Column = importlib.import_module("datapipe.catalog").Column
    Table = importlib.import_module("datapipe.catalog").Table
    Checkpoint = importlib.import_module("datapipe.checkpoints").Checkpoint
    preflight = importlib.import_module("datapipe.manifests").preflight
    preview = importlib.import_module("datapipe.replay_plan").preview

    point = datetime(2026, 10, 1, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for kind, values, reject in (
            ("integer", ("01", "1"), True),
            ("real", ("1.0", "1e0"), True),
            ("text", ("01", "1"), False),
        ):
            table = Table(
                "orders", (Column("id", kind), Column("region", "text")), ("id", "region")
            )
            catalog = {"orders": table}
            entries = []
            for index, value in enumerate(values):
                body = f"id,region\n{value},west\n".encode()
                name = f"part-{index}.csv"
                (root / name).write_bytes(body)
                entries.append(
                    {
                        "table": "orders",
                        "file": name,
                        "rows": 1,
                        "checksum": hashlib.sha256(body).hexdigest(),
                    }
                )
            document = {"version": 1, "extracts": entries}
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            require(
                refuses(preflight, document, root, catalog) == reject,
                f"cross-shard {kind} identity differs in preflight",
            )
            require(
                refuses(
                    preview,
                    Checkpoint("orders", 0, 0),
                    [],
                    point,
                    point,
                    document,
                    root,
                    catalog,
                    catalog,
                )
                == reject,
                f"cross-shard {kind} identity differs in preview",
            )
            require(
                {p.name: p.read_bytes() for p in root.iterdir()} == before,
                "cross-shard refusal wrote state",
            )
            # The same numeric key in another region or table is distinct.
            body = f"id,region\n{values[1]},east\n".encode()
            (root / "part-1.csv").write_bytes(body)
            entries[1]["checksum"] = hashlib.sha256(body).hexdigest()
            require(
                preflight(document, root, catalog)["rows"] == {"orders": 2},
                "cross-shard check collapsed composite keys",
            )
            body = (root / "part-0.csv").read_bytes()
            (root / "part-1.csv").write_bytes(body)
            entries[1].update(table="events", checksum=hashlib.sha256(body).hexdigest())
            catalog["events"] = Table("events", table.columns, table.key)
            require(
                preflight(document, root, catalog)["rows"] == {"orders": 1, "events": 1},
                "cross-shard check merged table namespaces",
            )


def dispatch():
    pending = importlib.import_module("datapipe.dispatch").pending

    jobs = read("data/retry-jobs.json")
    receipts = read("data/delivery-receipts.json")
    require(
        pending(jobs, receipts) == [jobs[1], jobs[0]], "retry identity lost a sibling or generation"
    )
    first = jobs[0]
    same = {"feed": "alpha", "part": 1, "generation": 3}
    history = [{**same, "status": "committed"}, {**same, "status": "failed"}]
    before = copy.deepcopy((jobs, receipts))
    require(pending([first, first], receipts) == [first], "retry duplicate was not coalesced")
    require(pending([first], history) == [], "failed retry reopened committed work")
    require(
        refuses(pending, [first, {**first, "file": "conflict.csv"}], history),
        "conflicting retry files accepted",
    )
    require((jobs, receipts) == before, "retry dispatch changed caller input")


def nightly():
    parse = importlib.import_module("datapipe.catalog").parse
    build = importlib.import_module("datapipe.nightly").build

    build = read_only(build)

    inventory = read("data/copies.json")
    catalog = parse(read("data/restore-catalog.json"))
    receipts = read("data/delivery-receipts.json")
    args = ("data/nightly.sqlite", DAY, Path("data/restore"), inventory, catalog, receipts)
    require(build(*args) == PLAN, "combined queue bypassed a hold or validation")
    require(read("docs/nightly-plan.json") == PLAN, "saved nightly queue differs")
    # Repair the missing copy and shard collision: both feeds must now queue completely.
    body = Path("data/restore/epsilon-1.csv").read_bytes()
    inventory = [
        {**row, "checksum": hashlib.sha256(body).hexdigest()}
        if row["file"] == "epsilon-1.csv"
        else row
        for row in inventory
    ]
    body = b"id,note\n2,b\n"
    Path("data/restore/zeta-1.csv").write_bytes(body)
    inventory = [
        {**row, "checksum": hashlib.sha256(body).hexdigest()}
        if row["file"] == "zeta-1.csv"
        else row
        for row in inventory
    ]
    result = build(args[0], DAY, args[2], inventory, catalog, receipts)
    require(
        result
        == {
            "jobs": [
                PLAN["jobs"][0],
                {"feed": "epsilon", "part": 0, "generation": 1, "file": "epsilon-0.csv"},
                {"feed": "epsilon", "part": 1, "generation": 1, "file": "epsilon-1.csv"},
                {"feed": "zeta", "part": 0, "generation": 2, "file": "zeta-0.csv"},
                {"feed": "zeta", "part": 1, "generation": 2, "file": "zeta-1.csv"},
            ],
            "held": [PLAN["held"][0], PLAN["held"][2]],
        },
        "combined queue hardcoded the seed holds",
    )
    require(
        build(args[0], "empty", args[2], inventory, catalog, receipts) == {"jobs": [], "held": []},
        "combined queue invented work on an empty day",
    )


if __name__ == "__main__":
    {
        "audit": audit,
        "restore-copies": copies,
        "shards": shards,
        "retry-identity": dispatch,
        "nightly-plan": nightly,
    }[sys.argv[1]]()
    print("PASS")
