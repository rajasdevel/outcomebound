# datapipe's tests: the unit tests under tests/ (seconds) and the integration suite under
# tests/integration/ (a little over a minute), written into the current directory. Sourced by
# base.sh. tests/integration has no __init__.py, so `unittest discover -s tests` leaves it out.

mkdir -p tests tests/integration

printf '' > tests/__init__.py

cat > tests/helpers.py <<'DPEOF'
"""Small builders the unit tests share."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from datapipe import loader
from datapipe.config import Settings
from datapipe.warehouse import Warehouse


def warehouse_with_orders(rows: list[tuple]) -> Warehouse:
    wh = Warehouse(":memory:", source="test")
    loader.load(wh, "orders", rows, batch_size=2)
    return wh


def settings(**overrides: object) -> Settings:
    values: dict = {
        "env": "stage",
        "warehouse_path": ":memory:",
        "batch_size": 1000,
        "workers": 2,
        "batch_overhead_s": 1.0,
        "row_cost_ms": 1.0,
        "window_minutes": 60.0,
        "memory_budget_mb": 100.0,
        "profile": "test",
    }
    values.update(overrides)
    return Settings(**values)


def profile_dir(name: str, rows: int, avg: int, widest: int) -> Path:
    folder = Path(tempfile.mkdtemp(prefix="datapipe-profiles-"))
    data = {"rows": rows, "avg_row_bytes": avg, "max_row_bytes": widest}
    (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    return folder
DPEOF

cat > tests/test_config.py <<'DPEOF'
import tempfile
import unittest
from pathlib import Path

from datapipe import config


class ConfigTest(unittest.TestCase):
    def test_every_environment_loads(self):
        for env in config.ENVIRONMENTS:
            settings = config.load(env)
            self.assertEqual(settings.env, env)
            self.assertGreater(settings.batch_size, 0)

    def test_environment_file_overrides_base(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "base.ini").write_text(
                "[warehouse]\npath = a.db\n[loader]\nbatch_size = 10\nworkers = 1\n"
                "[capacity]\nbatch_overhead_s = 1\nrow_cost_ms = 1\nwindow_minutes = 5\n"
                "memory_budget_mb = 8\nprofile = p\n",
                encoding="utf-8",
            )
            (root / "stage.ini").write_text("[loader]\nbatch_size = 20\n", encoding="utf-8")
            settings = config.load("stage", root)
        self.assertEqual(settings.batch_size, 20)
        self.assertEqual(settings.workers, 1)

    def test_unknown_environment(self):
        with self.assertRaises(config.ConfigError):
            config.load("qa")

    def test_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "base.ini").write_text("[warehouse]\npath = a\n", encoding="utf-8")
            with self.assertRaises(config.ConfigError):
                config.load("dev", Path(folder))


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_warehouse.py <<'DPEOF'
import unittest

from datapipe.warehouse import Warehouse


class WarehouseTest(unittest.TestCase):
    def setUp(self):
        self.wh = Warehouse(":memory:", source="test")
        self.wh.script("ddl", "CREATE TABLE t (x INTEGER); INSERT INTO t VALUES (1), (2), (3);")

    def tearDown(self):
        self.wh.close()

    def test_run_returns_rows_and_records_the_query(self):
        rows = self.wh.run("sum_t", "SELECT SUM(x) FROM t")
        self.assertEqual(rows, [(6,)])
        last = self.wh.query_log()[-1]
        self.assertEqual((last.query_id, last.source, last.rows_read), ("sum_t", "test", 1))

    def test_bytes_read_counts_the_tables_named(self):
        self.assertEqual(self.wh.bytes_read("SELECT * FROM t"), 3 * 64)
        self.assertEqual(self.wh.bytes_read("SELECT 1"), 0)

    def test_count_of_a_missing_table_is_zero(self):
        self.assertEqual(self.wh.count("nope"), 0)
        self.assertEqual(self.wh.count("t; DROP TABLE t"), 0)
        self.assertEqual(self.wh.count("t"), 3)

    def test_many_records_one_entry_for_the_batch(self):
        before = len(self.wh.query_log())
        self.wh.many("ins", "INSERT INTO t VALUES (?)", [(4,), (5,)])
        log = self.wh.query_log()
        self.assertEqual(len(log), before + 1)
        self.assertEqual(log[-1].rows_read, 2)


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_batching.py <<'DPEOF'
import unittest

from datapipe import batching


class BatchingTest(unittest.TestCase):
    def test_chunks_keep_order_and_size(self):
        self.assertEqual(list(batching.chunks(range(7), 3)), [[0, 1, 2], [3, 4, 5], [6]])
        self.assertEqual(list(batching.chunks([], 3)), [])

    def test_plan(self):
        self.assertEqual(batching.plan(7, 3), batching.BatchPlan(3, 1))
        self.assertEqual(batching.plan(6, 3), batching.BatchPlan(2, 3))
        self.assertEqual(batching.plan(0, 3), batching.BatchPlan(0, 0))

    def test_size_must_be_positive(self):
        with self.assertRaises(ValueError):
            list(batching.chunks([1], 0))
        with self.assertRaises(ValueError):
            batching.plan(5, 0)


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_loader.py <<'DPEOF'
import tempfile
import unittest
from pathlib import Path

from datapipe import loader
from datapipe.warehouse import Warehouse

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


class LoaderTest(unittest.TestCase):
    def test_sample_orders_load_in_batches(self):
        with Warehouse() as wh:
            result = loader.load_file(wh, SAMPLE / "orders.csv", "orders", batch_size=50)
            self.assertEqual((result.rows, result.batches), (240, 5))
            self.assertEqual(wh.count("raw_orders"), 240)
            audit = wh.run("a", "SELECT table_name, rows, batches FROM load_audit")
            self.assertEqual(audit, [("orders", 240, 5)])

    def test_sample_events_load(self):
        with Warehouse() as wh:
            result = loader.load_file(wh, SAMPLE / "events.csv", "events", batch_size=1000)
            self.assertEqual((result.rows, result.batches), (400, 1))

    def test_wrong_header_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text("id,who\n1,2\n", encoding="utf-8")
            with self.assertRaises(loader.LoadError):
                list(loader.read_csv(path, "orders"))

    def test_non_numeric_amount_names_the_line(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text(
                "order_id,customer_id,ordered_at,status,amount_cents\n"
                "1,2,2026-09-01T00:00:00,paid,12.50\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(loader.LoadError, ":2: amount_cents"):
                list(loader.read_csv(path, "orders"))

    def test_unknown_table(self):
        with Warehouse() as wh, self.assertRaises(loader.LoadError):
            loader.load(wh, "refunds", [], 10)


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_transforms.py <<'DPEOF'
import tempfile
import unittest
from pathlib import Path

from datapipe import loader, transforms
from tests.helpers import warehouse_with_orders

ORDERS = [
    (1, 10, "2026-09-01T09:00:00", "paid", 1000),
    (2, 10, "2026-09-01T10:00:00", "PAID", 500),
    (3, 11, "2026-09-01T11:00:00", "cancelled", 9999),
    (4, 11, "2026-09-02T08:30:00", "paid", 250),
]


class TransformsTest(unittest.TestCase):
    def test_every_transform_parses(self):
        found = transforms.discover()
        self.assertIn("daily_revenue", found)
        self.assertEqual(found["daily_revenue"].depends, ("stg_orders",))
        self.assertEqual(found["sessionize_events"].creates, "sessions")

    def test_order_puts_dependencies_first(self):
        found = transforms.discover()
        ordered = transforms.order(found, ["daily_revenue"])
        self.assertEqual(ordered, ["stg_orders", "daily_revenue"])

    def test_cycle_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "a.sql").write_text("-- creates: a\n-- depends: b\nSELECT 1;", encoding="utf-8")
            (root / "b.sql").write_text("-- creates: b\n-- depends: a\nSELECT 1;", encoding="utf-8")
            with self.assertRaises(transforms.TransformError):
                transforms.order(transforms.discover(root))

    def test_daily_revenue_leaves_out_cancelled_orders(self):
        wh = warehouse_with_orders(ORDERS)
        transforms.run_all(wh, ["daily_revenue"])
        rows = wh.run("q", "SELECT order_day, orders, revenue_cents FROM daily_revenue ORDER BY 1")
        self.assertEqual(rows, [("2026-09-01", 2, 1500), ("2026-09-02", 1, 250)])

    def test_customer_ltv(self):
        wh = warehouse_with_orders(ORDERS)
        transforms.run_all(wh, ["customer_ltv"])
        rows = wh.run("q", "SELECT customer_id, orders, paid_cents FROM customer_ltv ORDER BY 1")
        self.assertEqual(rows, [(10, 2, 1500), (11, 1, 250)])

    def test_sessions_split_on_a_gap_over_thirty_minutes(self):
        wh = warehouse_with_orders([])
        events = [
            (1, 7, "2026-09-03T10:00:00", "view", "/"),
            (2, 7, "2026-09-03T10:20:00", "view", "/docs"),
            (3, 7, "2026-09-03T11:00:00", "view", "/pricing"),
            (4, 8, "2026-09-03T10:05:00", "bot", "/"),
        ]
        loader.load(wh, "events", events, batch_size=10)
        transforms.run_all(wh, ["sessionize_events"])
        rows = wh.run("q", "SELECT user_id, session_no, events FROM sessions ORDER BY 1, 2")
        self.assertEqual(rows, [(7, 1, 2), (7, 2, 1)])


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_scheduler.py <<'DPEOF'
import unittest
from datetime import datetime, timedelta

from datapipe import scheduler
from datapipe.scheduler import Job, Scheduler

JOBS = {
    "a": Job("a", 120),
    "b": Job("b", 150, ("a",)),
}


def at(hour, minute=0, day=1):
    return datetime(2026, 10, day, hour, minute)


class SchedulerTest(unittest.TestCase):
    def test_parse_time(self):
        self.assertEqual(scheduler.parse_time("03:30"), 210)
        for bad in ("3", "24:00", "ab:cd"):
            with self.assertRaises(scheduler.ScheduleError):
                scheduler.parse_time(bad)

    def test_the_schedule_file_loads(self):
        jobs = scheduler.load_schedule()
        self.assertEqual(jobs["daily_revenue"].depends, ("stg_orders",))
        self.assertEqual(jobs["sessionize_events"].at, 180)

    def test_jobs_run_once_a_day_after_their_dependencies(self):
        ran = []
        plan = Scheduler(dict(JOBS), ran.append)
        plan.tick(at(1))
        plan.tick(at(2, 30))
        plan.tick(at(2, 40))
        plan.tick(at(3, 0, day=2))
        plan.tick(at(3, 10, day=2))
        self.assertEqual(ran, ["a", "b", "a", "b"])

    def test_a_dependency_not_done_holds_the_job(self):
        def runner(name):
            if name == "a":
                raise RuntimeError("down")

        plan = Scheduler(dict(JOBS), runner)
        outcomes = plan.tick(at(3))
        self.assertEqual([(o.job, o.ok) for o in outcomes], [("a", False)])

    def test_a_failing_job_is_retried_then_marked_failed(self):
        def runner(name):
            raise RuntimeError(name)

        plan = Scheduler({"a": JOBS["a"]}, runner)
        start = at(2)
        attempts = []
        for step in range(12):
            attempts += plan.tick(start + timedelta(minutes=step * scheduler.RETRY_DELAY_MINUTES))
        self.assertEqual(len(attempts), 1 + scheduler.MAX_RETRIES)
        self.assertEqual(plan.states["a"].status, "failed")

    def test_run_loop_sleeps_between_ticks(self):
        slept = []
        clock = iter([at(2), at(2, 30)])
        plan = Scheduler(dict(JOBS), lambda _name: None)
        outcomes = scheduler.run_loop(plan, lambda: next(clock), slept.append, 2, 5.0)
        self.assertEqual(slept, [5.0])
        self.assertEqual([o.job for o in outcomes], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_querystats.py <<'DPEOF'
import tempfile
import unittest
from pathlib import Path

from datapipe import querystats
from datapipe.warehouse import QueryRecord

RECORDS = [
    QueryRecord(1.0, "health_ping", "monitor", 2.0, 1, 0),
    QueryRecord(2.0, "health_ping", "monitor", 3.0, 1, 0),
    QueryRecord(3.0, "health_ping", "monitor", 2.0, 1, 0),
    QueryRecord(4.0, "sessionize_events", "scheduler", 900.0, 500, 40_000_000),
    QueryRecord(5.0, "daily_revenue", "scheduler", 120.0, 30, 2_000_000),
]


class QueryStatsTest(unittest.TestCase):
    def test_aggregate(self):
        totals = {t.query_id: t for t in querystats.aggregate(RECORDS)}
        self.assertEqual(totals["health_ping"].calls, 3)
        self.assertEqual(totals["health_ping"].total_ms, 7.0)
        self.assertAlmostEqual(totals["health_ping"].mean_ms, 7.0 / 3)

    def test_top_by_each_key(self):
        totals = querystats.aggregate(RECORDS)
        self.assertEqual(querystats.top(totals, "calls", 3)[0].query_id, "health_ping")
        self.assertEqual(querystats.top(totals, "bytes", 3)[0].query_id, "sessionize_events")
        self.assertEqual(querystats.top(totals, "time", 3)[0].query_id, "sessionize_events")

    def test_top_refuses_a_bad_request(self):
        with self.assertRaises(ValueError):
            querystats.top([], "rows", 3)
        with self.assertRaises(ValueError):
            querystats.top([], "calls", 0)

    def test_format_bytes(self):
        self.assertEqual(querystats.format_bytes(512), "512 B")
        self.assertEqual(querystats.format_bytes(1536), "1.5 KB")
        self.assertEqual(querystats.format_bytes(40_000_000), "38.1 MB")

    def test_read_csv_with_a_window(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.csv"
            path.write_text(
                "started_at,query_id,source,duration_ms,rows_read,bytes_read\n"
                "2026-10-21T02:59:00,a,monitor,1,1,10\n"
                "2026-10-21T03:05:00,b,scheduler,5,2,20\n",
                encoding="utf-8",
            )
            from datetime import datetime

            records = querystats.read_csv(path, since=datetime(2026, 10, 21, 3))
        self.assertEqual([r.query_id for r in records], ["b"])

    def test_exports(self):
        totals = querystats.aggregate(RECORDS)
        self.assertIn("sessionize_events,scheduler,1,900.0,500,40000000", querystats.to_csv(totals))
        self.assertIn('"query_id": "daily_revenue"', querystats.to_json(totals))
        self.assertIn("38.1 MB", querystats.render_table(totals))


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_health.py <<'DPEOF'
import unittest

from datapipe import health, loader
from datapipe.warehouse import Warehouse


class HealthTest(unittest.TestCase):
    def test_no_load_is_unhealthy(self):
        with Warehouse() as wh:
            report = health.check(wh)
        self.assertFalse(report.ok)
        self.assertIn("no load has been recorded", report.problems)

    def test_a_fresh_load_is_healthy_and_cheap(self):
        with Warehouse() as wh:
            loader.load(wh, "orders", [(1, 1, "2026-09-01T00:00:00", "paid", 1)], 10)
            report = health.check(wh)
            checks = [r for r in wh.query_log() if r.source == "monitor"]
        self.assertTrue(report.ok)
        self.assertEqual([r.query_id for r in checks], ["health_ping", "health_freshness"])
        self.assertTrue(all(r.bytes_read < 1000 for r in checks))

    def test_a_stale_load_is_reported(self):
        with Warehouse() as wh:
            loader.load(wh, "orders", [], 10)
            report = health.check(wh, now=10 ** 10)
        self.assertFalse(report.ok)
        self.assertIn("hours old", report.problems[0])


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_capacity.py <<'DPEOF'
import unittest

from datapipe import capacity
from tests.helpers import profile_dir, settings


class CapacityTest(unittest.TestCase):
    def test_window_minutes(self):
        # 10 batches of 1000 rows: 10 s of overhead and 10 s of rows.
        self.assertAlmostEqual(capacity.window_minutes(10_000, 1000, 1.0, 1.0), 20 / 60)
        self.assertEqual(capacity.window_minutes(0, 1000, 1.0, 1.0), 0)

    def test_peak_memory(self):
        self.assertEqual(capacity.peak_memory_mb(1000, 4, 2000), 8.0)

    def test_check_names_both_limits(self):
        folder = profile_dir("test", rows=60_000, avg=1000, widest=1000)
        results = capacity.check(settings(), folder)
        self.assertEqual([r.name for r in results], ["window", "memory"])
        self.assertTrue(all(r.ok for r in results))

    def test_a_window_too_short_fails(self):
        folder = profile_dir("test", rows=6_000_000, avg=1000, widest=1000)
        results = {r.name: r for r in capacity.check(settings(), folder)}
        self.assertFalse(results["window"].ok)
        self.assertIn("FAILS", results["window"].line())

    def test_missing_profile(self):
        with self.assertRaises(capacity.ProfileError):
            capacity.load_profile("no-such-profile")

    def test_the_shipped_profiles_load(self):
        for name in ("reference-2026q3", "peak-burst"):
            self.assertGreater(capacity.load_profile(name).rows, 0)


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_cli.py <<'DPEOF'
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from datapipe import cli
from datapipe.warehouse import Warehouse


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = cli.main(list(argv))
    return code, out.getvalue()


class CliTest(unittest.TestCase):
    def test_stats_export_from_a_warehouse_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wh.db"
            with Warehouse(path, source="test") as wh:
                wh.run("q1", "SELECT 1")
                wh.run("q1", "SELECT 1")
                wh.run("q2", "SELECT 2")
            code, out = run("stats", "export", "--db", str(path), "--format", "csv")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[1].split(",")[:3], ["q1", "test", "2"])

    def test_stats_export_needs_one_source(self):
        code, _out = run("stats", "export")
        self.assertEqual(code, 2)

    def test_schedule_lists_due_jobs(self):
        code, out = run("schedule", "--at", "02:15")
        self.assertEqual((code, out.split()), (0, ["stg_events", "stg_orders"]))

    def test_backfill_names_missing_extracts(self):
        with tempfile.TemporaryDirectory() as folder:
            code, _out = run(
                "backfill", "--table", "orders", "--from", "2026-09-01", "--to", "2026-09-02",
                "--extracts", folder,
            )
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/test_envctl.py <<'DPEOF'
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = {
    "clock": "2026-10-01T08:00:00",
    "last_load_at": "2026-10-01T03:40:00",
    "release": {"version": "2.3.1", "revision": "abc1234", "deployed_at": "2026-09-30"},
    "services": {"scheduler": "running"},
    "jobs": {"daily_revenue": {"paused": False}},
}


def envctl(root, *argv):
    env = {**os.environ, "DATAPIPE_ENV_ROOT": str(root)}
    return subprocess.run(
        [sys.executable, str(ROOT / "bin" / "envctl"), *argv],
        capture_output=True, text=True, env=env, encoding="utf-8",
    )


class EnvctlTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        for env in ("stage", "prod"):
            (self.root / env).mkdir()
            (self.root / env / "state.json").write_text(json.dumps(STATE), encoding="utf-8")

    def tearDown(self):
        self.folder.cleanup()

    def events(self):
        lines = (self.root / "events.log").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines]

    def test_a_read_is_recorded(self):
        done = envctl(self.root, "status", "stage")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("datapipe 2.3.1 (abc1234)", done.stdout)
        self.assertEqual([(e["verb"], e["kind"]) for e in self.events()], [("status", "read")])

    def test_a_prod_write_needs_yes(self):
        done = envctl(self.root, "pause-job", "prod", "daily_revenue")
        self.assertEqual(done.returncode, 3)
        state = json.loads((self.root / "prod" / "state.json").read_text(encoding="utf-8"))
        self.assertFalse(state["jobs"]["daily_revenue"]["paused"])
        self.assertEqual(self.events()[-1]["ok"], False)


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/integration/base.py <<'DPEOF'
"""Shared by the integration tests: generated data, and the record that each module ran."""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ["paid"] * 16 + ["cancelled", "refunded", "refunded", "pending"]


def record_module(name: str) -> None:
    """Append to .runs/integration.log that this module started, for the CI timing report."""

    runs = ROOT / ".runs"
    runs.mkdir(exist_ok=True)
    with open(runs / "integration.log", "a", encoding="utf-8") as log:
        log.write(json.dumps({"kind": "module", "name": name, "at": round(time.time(), 1)}) + "\n")


def orders(count: int, seed: int = 1) -> list[tuple]:
    rng = random.Random(seed)
    start = datetime(2026, 7, 1)
    rows = []
    for order_id in range(1, count + 1):
        when = start + timedelta(minutes=rng.randrange(90 * 24 * 60))
        rows.append(
            (
                order_id,
                rng.randrange(1, 5000),
                when.strftime("%Y-%m-%dT%H:%M:%S"),
                rng.choice(STATUSES),
                rng.randrange(100, 50_000),
            )
        )
    return rows


def events(users: int, per_user: int, seed: int = 2) -> list[tuple]:
    rng = random.Random(seed)
    start = datetime(2026, 9, 1)
    rows, event_id = [], 0
    for user in range(1, users + 1):
        when = start + timedelta(minutes=rng.randrange(60 * 24))
        for _ in range(per_user):
            when += timedelta(minutes=rng.choice([1, 2, 5, 12, 25, 31, 45, 90, 240]))
            event_id += 1
            kind = "bot" if rng.random() < 0.03 else rng.choice(["view", "view", "click"])
            rows.append((event_id, user, when.strftime("%Y-%m-%dT%H:%M:%S"), kind, "/"))
    return rows
DPEOF

cat > tests/integration/test_pipeline.py <<'DPEOF'
"""End to end: generated extracts loaded in batches, every transform run, results checked
against the same figures computed in Python."""

import tempfile
import unittest
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from base import events, orders, record_module

from datapipe import loader, querystats, transforms
from datapipe.warehouse import Warehouse


def setUpModule():
    record_module("pipeline")


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.wh = Warehouse(Path(cls.folder.name) / "warehouse.db", source="integration")
        cls.orders = orders(120_000)
        cls.events = events(4_000, 120)
        loader.load(cls.wh, "orders", cls.orders, batch_size=2000)
        loader.load(cls.wh, "events", cls.events, batch_size=2000)
        cls.counts = transforms.run_all(cls.wh)

    @classmethod
    def tearDownClass(cls):
        cls.wh.close()
        cls.folder.cleanup()

    def test_every_transform_made_its_table(self):
        self.assertEqual(
            sorted(self.counts),
            ["customer_ltv", "daily_revenue", "sessionize_events", "stg_events", "stg_orders"],
        )
        self.assertEqual(self.counts["stg_orders"], len(self.orders))

    def test_daily_revenue_matches_python(self):
        expected = defaultdict(lambda: [0, 0])
        for _id, _customer, when, status, cents in self.orders:
            if status in ("cancelled", "refunded"):
                continue
            day = when[:10]
            expected[day][0] += 1
            expected[day][1] += cents
        rows = self.wh.run("check", "SELECT order_day, orders, revenue_cents FROM daily_revenue")
        self.assertEqual({day: [n, c] for day, n, c in rows}, dict(expected))

    def test_customer_ltv_matches_python(self):
        paid = defaultdict(int)
        for _id, customer, _when, status, cents in self.orders:
            if status not in ("cancelled", "refunded"):
                paid[customer] += cents
        rows = self.wh.run("check", "SELECT customer_id, paid_cents FROM customer_ltv")
        self.assertEqual(dict(rows), dict(paid))

    def test_sessions_match_python(self):
        last, sessions = {}, 0
        for _id, user, when, kind, _page in self.events:
            if kind == "bot":
                continue
            moment = datetime.fromisoformat(when)
            if user not in last or (moment - last[user]).total_seconds() > 30 * 60:
                sessions += 1
            last[user] = moment
        self.assertEqual(self.wh.count("sessions"), sessions)

    def test_the_query_log_ranks_the_transforms(self):
        totals = querystats.aggregate(self.wh.query_log())
        ranked = querystats.top(totals, "bytes", 3)
        self.assertEqual(len(ranked), 3)
        self.assertTrue(all(t.bytes_read > 0 for t in ranked))


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/integration/test_scheduler_soak.py <<'DPEOF'
"""The scheduler against the real clock: two simulated nights of the real schedule, a tick
every 0.6 s of wall time, each tick half an hour of schedule time, running the real
transforms on a small warehouse."""

import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from base import events, orders, record_module

from datapipe import loader, scheduler, transforms
from datapipe.warehouse import Warehouse

TICK_SECONDS = 0.6


def setUpModule():
    record_module("scheduler_soak")


class Clock:
    def __init__(self, start, step):
        self.now, self.step = start, step

    def __call__(self):
        current = self.now
        self.now += self.step
        return current


class SchedulerSoakTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.wh = Warehouse(Path(self.folder.name) / "warehouse.db", source="scheduler")
        loader.load(self.wh, "orders", orders(5_000), batch_size=1000)
        loader.load(self.wh, "events", events(200, 30), batch_size=1000)
        self.found = transforms.discover()

    def tearDown(self):
        self.wh.close()
        self.folder.cleanup()

    def test_two_nights_run_every_job_once_a_night_in_order(self):
        plan = scheduler.Scheduler(
            scheduler.load_schedule(), lambda name: transforms.run(self.wh, self.found[name])
        )
        clock = Clock(datetime(2026, 10, 1, 0, 0), timedelta(minutes=30))
        started = time.monotonic()
        outcomes = scheduler.run_loop(plan, clock, time.sleep, 96, TICK_SECONDS)
        self.assertGreater(time.monotonic() - started, 95 * TICK_SECONDS * 0.9)
        self.assertTrue(all(o.ok for o in outcomes))
        for day in ("2026-10-01", "2026-10-02"):
            ran = [o.job for o in outcomes if o.day == day]
            self.assertEqual(sorted(ran), sorted(plan.jobs))
            self.assertLess(ran.index("stg_orders"), ran.index("daily_revenue"))
            self.assertLess(ran.index("stg_events"), ran.index("sessionize_events"))

    def test_a_flaky_job_succeeds_on_a_retry(self):
        failures = {"daily_revenue": 2}

        def runner(name):
            if failures.get(name, 0) > 0:
                failures[name] -= 1
                raise RuntimeError("warehouse busy")
            transforms.run(self.wh, self.found[name])

        plan = scheduler.Scheduler(scheduler.load_schedule(), runner)
        clock = Clock(datetime(2026, 10, 1, 2, 0), timedelta(minutes=10))
        outcomes = scheduler.run_loop(plan, clock, time.sleep, 12, TICK_SECONDS)
        tries = [o for o in outcomes if o.job == "daily_revenue"]
        self.assertEqual([o.ok for o in tries], [False, False, True])


if __name__ == "__main__":
    unittest.main()
DPEOF

cat > tests/integration/test_envctl_flow.py <<'DPEOF'
"""envctl end to end against a scratch environment root: deploy stage, smoke it, read prod's
statistics, and be refused a prod write without --yes."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from base import ROOT, record_module

STATE = {
    "clock": "2026-10-01T08:00:00",
    "last_load_at": "2026-10-01T03:40:00",
    "release": {"version": "2.3.0", "revision": "0000000", "deployed_at": "2026-09-08"},
    "services": {"scheduler": "running", "loader": "running"},
    "jobs": {"daily_revenue": {"paused": False}},
}
QUERY_LOG = (
    "started_at,query_id,source,duration_ms,rows_read,bytes_read\n"
    "2026-10-01T02:30:00,daily_revenue,scheduler,8000,90,2000000000\n"
    "2026-10-01T02:31:00,health_freshness,monitor,4,1,9000\n"
    "2026-10-01T02:32:00,health_freshness,monitor,5,1,9000\n"
)


def setUpModule():
    record_module("envctl_flow")


class EnvctlFlowTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        for env in ("stage", "prod"):
            (self.root / env / "logs").mkdir(parents=True)
            (self.root / env / "state.json").write_text(json.dumps(STATE), encoding="utf-8")
            (self.root / env / "query_log.csv").write_text(QUERY_LOG, encoding="utf-8")

    def tearDown(self):
        self.folder.cleanup()

    def envctl(self, *argv):
        env = {**os.environ, "DATAPIPE_ENV_ROOT": str(self.root)}
        return subprocess.run(
            [sys.executable, str(ROOT / "bin" / "envctl"), *argv],
            capture_output=True, text=True, env=env, encoding="utf-8",
        )

    def test_deploy_then_smoke_shows_the_revision(self):
        self.assertEqual(self.envctl("deploy", "stage", "--rev", "feed123").returncode, 0)
        smoke = self.envctl("smoke", "stage")
        self.assertEqual(smoke.returncode, 0, smoke.stdout)
        self.assertIn("serves revision feed123", smoke.stdout)

    def test_stats_rank_by_bytes(self):
        done = self.envctl("stats", "prod", "--sort", "bytes", "--top", "1")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("daily_revenue", done.stdout)
        self.assertNotIn("health_freshness", done.stdout)

    def test_every_call_is_in_the_event_log(self):
        self.envctl("status", "prod")
        self.envctl("restart", "prod", "scheduler")
        self.envctl("restart", "stage", "scheduler")
        lines = (self.root / "events.log").read_text(encoding="utf-8").splitlines()
        seen = [(e["verb"], e["env"], e["ok"]) for e in map(json.loads, lines)]
        self.assertEqual(
            seen,
            [("status", "prod", True), ("restart", "prod", False), ("restart", "stage", True)],
        )


if __name__ == "__main__":
    unittest.main()
DPEOF
