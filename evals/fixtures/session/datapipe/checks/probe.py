"Independent examples for caller-visible behavior, run only in a scratch project."

from __future__ import annotations

import configparser
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.getcwd())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def refuses(call, *args) -> bool:
    try:
        call(*args)
    except ValueError:
        return True
    return False


def manifest() -> None:
    module = importlib.import_module("datapipe.manifests")
    parse, total_rows = module.parse, module.total_rows

    def extract(file="a.csv", rows=2, table="orders"):
        return {"table": table, "file": file, "rows": rows, "checksum": "a" * 64}

    for entries in (
        [extract(), extract("./a.csv")],
        [extract(), extract("a.csv", table="events")],
        [extract(rows=True)],
    ):
        reject_manifest(entries)
    rows = parse({"version": 1, "extracts": [extract(rows=0), extract("b.csv", 3)]})
    require(total_rows(rows) == {"orders": 3}, "distinct same-table extracts must remain valid")
    require(parse({"version": 1, "extracts": []}) == [], "empty manifest must remain valid")
    preflight = module.preflight
    catalog = importlib.import_module("datapipe.catalog").parse(
        {
            "tables": [
                {
                    "name": "orders",
                    "key": ["id"],
                    "columns": [
                        {"name": "id", "kind": "integer", "nullable": False},
                        {"name": "note", "kind": "text", "nullable": True},
                    ],
                }
            ]
        }
    )
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        content = {"a.csv": "id,note\n1,first\n", "b.csv": "id,note\n2,\n3,last\n"}
        for name, body in content.items():
            (root / name).write_text(body, encoding="utf-8")
        entries = [
            {
                "table": "orders",
                "file": name,
                "rows": rows,
                "checksum": hashlib.sha256(content[name].encode()).hexdigest(),
            }
            for name, rows in (("a.csv", 1), ("b.csv", 2))
        ]
        before = {p.name: p.read_bytes() for p in root.iterdir()}
        require(
            preflight({"version": 1, "extracts": entries}, root, catalog)
            == {"files": 2, "rows": {"orders": 3}},
            "preflight totals differ",
        )
        require(
            preflight({"version": 1, "extracts": []}, root, catalog) == {"files": 0, "rows": {}},
            "empty preflight differs",
        )
        for change in (
            {"rows": 9},
            {"checksum": "0" * 64},
            {"file": "missing.csv"},
            {"table": "events"},
        ):
            bad = [entries[0], {**entries[1], **change}]
            try:
                preflight({"version": 1, "extracts": bad}, root, catalog)
            except ValueError:
                pass
            else:
                raise ValueError(f"preflight accepted {change}")
        (root / "alias.csv").symlink_to(root / "a.csv")
        try:
            preflight(
                {"version": 1, "extracts": [entries[0], {**entries[0], "file": "alias.csv"}]},
                root,
                catalog,
            )
        except ValueError:
            pass
        else:
            raise ValueError("preflight accepted two names for one resolved file")
        (root / "alias.csv").unlink()
        require({p.name: p.read_bytes() for p in root.iterdir()} == before, "preflight wrote files")
    expected_review = {
        f"feed_{number:02}": (
            [],
            ["type changed for attribute_2"],
            ["removed legacy_code"],
            ["primary key changed"],
        )[number % 4]
        for number in range(1, 17)
    }
    blocks = re.findall(
        r"```json\s*\n(.*?)\n```", Path("docs/extracts.md").read_text(encoding="utf-8"), re.S
    )
    require(any(feed_review(block) == expected_review for block in blocks), "feed review wrong")


def feed_review(block: str) -> object:
    """The differences a fenced block records by feed name, as one sorted list for each feed:
    a feed's list may stand alone or be grouped by table name."""

    try:
        review = json.loads(block)
    except ValueError:
        return None
    if not isinstance(review, dict):
        return None
    found = {}
    for feed, value in review.items():
        if isinstance(value, dict) and all(isinstance(item, list) for item in value.values()):
            value = [item for items in value.values() for item in items]
        if not isinstance(value, list):
            return None
        found[feed] = sorted(value)
    return found


def reject_manifest(entries: list[dict]) -> None:
    parse = importlib.import_module("datapipe.manifests").parse

    try:
        parse({"version": 1, "extracts": entries})
    except ValueError:
        return
    raise ValueError("duplicate normalized file or boolean row count accepted")


def replay() -> None:
    module = importlib.import_module("datapipe.watermarks")
    assign, windows = module.assign, module.windows

    times = [
        datetime.fromisoformat(value)
        for value in (
            "2026-10-01T00:00:00+00:00",
            "2026-10-01T01:00:00+00:00",
            "2026-10-01T02:30:00+00:00",
            "2026-10-01T03:00:00+02:00",
            "2026-09-30T23:59:59+00:00",
            "2026-10-01T02:29:59+00:00",
        )
    ]
    spans = windows(times[0], times[2])
    require(
        assign(times, spans) == [[0], [1, 3], [5]],
        "boundary event duplicated or final end included",
    )
    try:
        assign([datetime(2026, 10, 1)], spans)
    except ValueError:
        pass
    else:
        raise ValueError("naive event timestamp accepted")
    planner()


def planner(initial: bool = False) -> None:
    plan = importlib.import_module("datapipe.replay_plan").plan
    checkpoint = importlib.import_module("datapipe.checkpoints").Checkpoint("orders", 8, 2)
    at = datetime.fromisoformat
    start, end = at("2026-10-01T00:00:00+00:00"), at("2026-10-01T02:00:00+00:00")
    events = [
        {"offset": 10, "at": at("2026-10-01T03:00:00+02:00")},
        {"offset": 8, "at": at("2026-10-01T00:10:00+00:00")},
        {"offset": 9, "at": end},
        {"offset": 7, "at": start},
    ]
    require(
        plan(checkpoint, events, start, end)
        == {
            "source": "orders",
            "generation": 2,
            "windows": [[8], [10]],
            "deferred": [9],
            "next_offset": 11 if initial else 9,
        },
        "plan skipped a deferred offset or changed window order",
    )
    require(
        plan(checkpoint, [events[0]], start, end)["next_offset"] == (11 if initial else 8),
        "plan skipped an absent offset",
    )
    for bad in (
        [events[0], events[0]],
        [{"offset": True, "at": start}],
        [{"offset": -1, "at": start}],
        [{"offset": 8, "at": datetime(2026, 10, 1)}],
    ):
        refuse_event(plan, checkpoint, bad, start, end)
    require((checkpoint.offset, checkpoint.generation) == (8, 2), "planning advanced a checkpoint")
    preview_cases(initial)


def preview_cases(initial: bool = False) -> None:
    preview = importlib.import_module("datapipe.replay_plan").preview
    catalog_module = importlib.import_module("datapipe.catalog")
    checkpoint = importlib.import_module("datapipe.checkpoints").Checkpoint("orders", 8, 2)
    table = catalog_module.Table("orders", (catalog_module.Column("id", "integer"),), ("id",))
    catalog = {"orders": table}
    at = datetime.fromisoformat
    start, end = at("2026-10-01T00:00:00+00:00"), at("2026-10-01T02:00:00+00:00")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        body = b"id\n1\n"
        (root / "part.csv").write_bytes(body)
        entry = {
            "table": "orders",
            "file": "part.csv",
            "rows": 1,
            "checksum": hashlib.sha256(body).hexdigest(),
        }
        document = {"version": 1, "extracts": [entry]}
        events = [{"offset": 10, "at": start}, {"offset": 9, "at": end}, {"offset": 8, "at": start}]
        result = preview(checkpoint, events, start, end, document, root, catalog, catalog)
        require(
            result
            == {
                "preflight": {"files": 1, "rows": {"orders": 1}},
                "plan": {
                    "source": "orders",
                    "generation": 2,
                    "windows": [[8, 10], []],
                    "deferred": [9],
                    "next_offset": 11 if initial else 9,
                },
            },
            "preview bypassed preflight or the recovery plan",
        )
        for previous, bad in (
            ({}, document),
            (catalog, {"version": 1, "extracts": [entry, {**entry, "file": "missing.csv"}]}),
        ):
            require(
                refuses(preview, checkpoint, events, start, end, bad, root, catalog, previous),
                "preview accepted an incompatible schema or invalid later file",
            )
        old = {
            "orders": catalog_module.Table(
                "orders", (catalog_module.Column("id", "text"),), ("id",)
            )
        }
        try:
            preview(checkpoint, events, start, end, document, root, catalog, old)
        except ValueError:
            pass
        else:
            raise ValueError("preview ignored incompatible type changes")
        require(
            {path.name: path.read_bytes() for path in root.iterdir()} == {"part.csv": body},
            "preview wrote restore state",
        )


def typed_keys() -> None:
    inspector = importlib.import_module("datapipe.extract_io").inspect
    module = importlib.import_module("datapipe.catalog")
    preview = importlib.import_module("datapipe.replay_plan").preview
    checkpoint = importlib.import_module("datapipe.checkpoints").Checkpoint("orders", 0, 0)
    point = datetime.fromisoformat("2026-10-01T00:00:00+00:00")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for kind, cells, reject in (
            ("integer", "01\n1", True),
            ("real", "1.0\n1e0", True),
            ("text", "01\n1", False),
        ):
            table = module.Table("orders", (module.Column("id", kind),), ("id",))
            body = ("id\n" + cells + "\n").encode()
            path = root / "part.csv"
            path.write_bytes(body)
            document = {
                "version": 1,
                "extracts": [
                    {
                        "table": "orders",
                        "file": "part.csv",
                        "rows": 2,
                        "checksum": hashlib.sha256(body).hexdigest(),
                    }
                ],
            }
            for call, args in (
                (inspector, (path, table)),
                (
                    preview,
                    (
                        checkpoint,
                        [],
                        point,
                        point,
                        document,
                        root,
                        {"orders": table},
                        {"orders": table},
                    ),
                ),
            ):
                require(
                    refuses(call, *args) == reject,
                    f"typed {kind} key identity differs through {call.__name__}",
                )
            require(path.read_bytes() == body, "review check changed an extract")
        table = module.Table(
            "orders",
            (module.Column("id", "integer"), module.Column("region", "text")),
            ("id", "region"),
        )
        path.write_text("id,region\n01,a\n1,b\n", encoding="utf-8")
        require(inspector(path, table)["rows"] == 2, "composite key collapsed distinct regions")


def incident_policy(initial: bool = False) -> None:
    diagnose = importlib.import_module("datapipe.incidents").diagnose
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        query, alert, schedule = (root / name for name in ("query", "alert", "schedule"))
        query.write_text(
            "started_at,query_id,source,duration_ms,rows_read,bytes_read\n"
            "2026-10-01T03:00:00,scan,scheduler,1,1,80\n"
            "2026-10-01T03:01:00,manual,manual,1,1,9000\n"
            "2026-10-01T03:02:00,health_ping,monitor,1,1,2\n"
            "2026-10-01T03:03:00,scan,manual,1,1,5000\n",
            encoding="utf-8",
        )
        alert.write_text("", encoding="utf-8")
        schedule.write_text("", encoding="utf-8")
        row = diagnose(query, alert, schedule, ["2026-10-01"])["nights"][0]
        require(
            (row["heavy"], row["bytes"], row["health_bytes"])
            == (("manual", 9000, 2) if initial else ("scan", 80, 2)),
            "report ranking did not follow the source policy",
        )
        if initial:
            return
        query.write_text(
            query.read_text(encoding="utf-8")
            .replace("2026-10-01T03:00:00,", "2026-10-01T05:00:00+02:00,")
            .replace("2026-10-01T03:01:00,", "2026-10-01T03:01:00Z,"),
            encoding="utf-8",
        )
        require(
            diagnose(query, alert, schedule, ["2026-10-01"])["nights"][0] == row,
            "offset export changed the report window",
        )
        reader = importlib.import_module("datapipe.querystats").read_csv
        rows = reader(
            query,
            datetime.fromisoformat("2026-10-01T05:00:00+02:00"),
            datetime.fromisoformat("2026-10-01T03:01:00+00:00"),
        )
        require(
            len(rows) == 1 and rows[0].started_at == 1790823600.0,
            "read_csv changed the instant or included the final end",
        )
        done = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "datapipe",
                "stats",
                "export",
                "--csv",
                str(query),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
        require(
            done.returncode == 0 and len(json.loads(done.stdout)) == 4,
            "stats export cannot read mixed export clocks",
        )


def refuse_event(plan, checkpoint, bad, start, end) -> None:
    try:
        plan(checkpoint, bad, start, end)
    except ValueError:
        return
    raise ValueError("invalid replay event accepted")


def incident() -> None:
    incident_policy()
    diagnose = importlib.import_module("datapipe.incidents").diagnose
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        query, alert, schedule = (
            root / name for name in ("queries.csv", "alerts.log", "scheduler.log")
        )
        query.write_text(
            "started_at,query_id,source,duration_ms,rows_read,bytes_read\n"
            + "\n".join(
                (
                    "2026-10-01T02:00:00,export,manual,1,1,9000",
                    "2026-10-01T03:00:00,nightly_scan,scheduler,1,1,80",
                    "2026-10-01T03:01:00,health_ping,monitor,1,1,2",
                    "2026-10-02T03:00:00,nightly_scan,scheduler,1,1,90",
                    "2026-10-02T03:20:00,export,manual,1,1,9000",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        alert.write_text(
            "2026-10-01T03:10:00Z FIRING disk_read_mb_s high\n"
            "2026-10-02T03:10:00Z FIRING disk_read_mb_s high\n",
            encoding="utf-8",
        )
        schedule.write_text(
            "2026-10-01T03:00:00Z start nightly_scan\n2026-10-02T03:00:00Z START nightly_scan\n",
            encoding="utf-8",
        )
        days = ["2026-10-02", "2026-10-01", "2026-10-01", "2026-10-03"]
        expected = {
            "nights": [
                {
                    "day": "2026-10-01",
                    "heavy": "nightly_scan",
                    "bytes": 80,
                    "health_bytes": 2,
                    "firing": True,
                    "scheduled": True,
                },
                {
                    "day": "2026-10-02",
                    "heavy": "nightly_scan",
                    "bytes": 90,
                    "health_bytes": 0,
                    "firing": True,
                    "scheduled": True,
                },
                {
                    "day": "2026-10-03",
                    "heavy": None,
                    "bytes": 0,
                    "health_bytes": 0,
                    "firing": False,
                    "scheduled": False,
                },
            ],
            "recurring": ["nightly_scan"],
        }
        require(
            diagnose(query, alert, schedule, days) == expected,
            "incident join confuses calls, windows or distinct nights",
        )
        schedule.write_text("2026-10-01T02:00:00Z START nightly_scan\n", encoding="utf-8")
        require(
            diagnose(query, alert, schedule, days)["recurring"] == [],
            "recurrence inferred without scheduled evidence",
        )
    actual = diagnose(
        Path(".envs/prod/query_log.csv"),
        Path(".envs/prod/logs/alerts.log"),
        Path(".envs/prod/logs/scheduler.log"),
        ["2026-10-18", "2026-10-19", "2026-10-20", "2026-10-21"],
    )
    require(actual["recurring"] == ["sessionize_events"], "wrong recurring incident cause")
    blocks = re.findall(
        r"```json\s*\n(.*?)\n```", Path("docs/triage.md").read_text(encoding="utf-8"), re.S
    )
    require(
        any(json.loads(block) == actual for block in blocks),
        "triage facts differ from the observed nights",
    )


def capacity() -> None:
    stage = configparser.ConfigParser()
    stage.read("config/stage.ini", encoding="utf-8")
    require(stage["loader"]["batch_size"] == "2000", "batch reduction was undone")
    cases: tuple[tuple[str, dict[str, int], int], ...] = (
        ("stage", {}, 0),
        ("stage", {"reference-2026q3": 1350000, "peak-burst": 100}, 1),
        ("stage", {"reference-2026q3": 1250000, "peak-burst": 9000000}, 0),
    )
    originals = {
        name: Path(f"data/profiles/{name}.json").read_text(encoding="utf-8")
        for name in ("reference-2026q3", "peak-burst")
    }
    for env, profiles, expect in cases:
        for name, original in originals.items():
            value = json.loads(original)
            if name in profiles:
                value["rows"] = profiles[name]
            Path(f"data/profiles/{name}.json").write_text(json.dumps(value), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, "-B", "-m", "datapipe", "capacity", "--env", env],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
        require(
            (done.returncode == 0) == (expect == 0),
            f"capacity has wrong verdict for {profiles}: {done.stdout}",
        )


def docs() -> None:
    code = Path("datapipe/scheduler.py").read_text(encoding="utf-8")
    page = Path("docs/specs/scheduler.md").read_text(encoding="utf-8")
    require("MAX_RETRIES = 3" in code, "scheduler retry policy changed")
    require(bool(page.strip()), "scheduler spec missing")
    done = subprocess.run(
        [sys.executable, "-B", "tools/docs_check.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    require(done.returncode == 0, done.stdout + done.stderr)


def docs_wording() -> None:
    page = Path("docs/specs/scheduler.md").read_text(encoding="utf-8")
    require(
        "retried up to 3 times" in page and "retried up to 5 times" not in page,
        "scheduler spec still wrong",
    )


if __name__ == "__main__":
    {
        "manifest": manifest,
        "replay": replay,
        "replay-initial": lambda: planner(True),
        "incident-initial": lambda: incident_policy(True),
        "typed-keys": typed_keys,
        "incident": incident,
        "capacity": capacity,
        "docs": docs,
        "docs-wording": docs_wording,
    }[sys.argv[1]]()
