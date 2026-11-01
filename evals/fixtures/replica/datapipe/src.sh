# datapipe's package, its SQL transforms, its configuration and its dataset profiles, written
# into the current directory. Sourced by base.sh.

mkdir -p datapipe/sql config data/profiles data/sample

cat > datapipe/__init__.py <<'DPEOF'
"""datapipe: the nightly pipeline that loads, transforms and reports on warehouse data."""

__version__ = "2.3.1"
DPEOF

cat > datapipe/__main__.py <<'DPEOF'
from datapipe.cli import main

raise SystemExit(main())
DPEOF

cat > datapipe/config.py <<'DPEOF'
"""Settings for one environment: config/base.ini, overlaid with config/<env>.ini."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
ENVIRONMENTS = ("dev", "stage", "prod")


class ConfigError(Exception):
    """A configuration that cannot be read."""


@dataclass(frozen=True)
class Settings:
    env: str
    warehouse_path: str
    batch_size: int
    workers: int
    batch_overhead_s: float
    row_cost_ms: float
    window_minutes: float
    memory_budget_mb: float
    profile: str


def load(env: str = "dev", config_dir: Path = CONFIG_DIR) -> Settings:
    """The settings of `env`: base.ini first, then the environment's own file over it."""

    if env not in ENVIRONMENTS:
        raise ConfigError(f"unknown environment {env!r}; one of {', '.join(ENVIRONMENTS)}")
    parser = configparser.ConfigParser()
    files = [config_dir / "base.ini", config_dir / f"{env}.ini"]
    read = parser.read([str(path) for path in files if path.is_file()], encoding="utf-8")
    if not read:
        raise ConfigError(f"no configuration under {config_dir}")
    try:
        warehouse = parser["warehouse"]
        loader = parser["loader"]
        capacity = parser["capacity"]
        return Settings(
            env=env,
            warehouse_path=warehouse.get("path", ":memory:"),
            batch_size=loader.getint("batch_size"),
            workers=loader.getint("workers"),
            batch_overhead_s=capacity.getfloat("batch_overhead_s"),
            row_cost_ms=capacity.getfloat("row_cost_ms"),
            window_minutes=capacity.getfloat("window_minutes"),
            memory_budget_mb=capacity.getfloat("memory_budget_mb"),
            profile=capacity.get("profile"),
        )
    except (KeyError, ValueError, TypeError) as problem:
        raise ConfigError(f"configuration for {env} is incomplete: {problem}") from problem
DPEOF

cat > datapipe/warehouse.py <<'DPEOF'
"""The warehouse connection. SQLite stands in for the warehouse in development and tests.

Every statement run through `Warehouse` is recorded in the `query_log` table with when it
started, how long it took, the rows it returned or changed and an estimate of the bytes it
read, so the query statistics (datapipe.querystats) rank local queries the way the
warehouse's own statistics rank production ones.
"""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

QUERY_LOG_DDL = """
CREATE TABLE IF NOT EXISTS query_log (
    started_at REAL NOT NULL,
    query_id TEXT NOT NULL,
    source TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    rows_read INTEGER NOT NULL,
    bytes_read INTEGER NOT NULL
)
"""
# SQLite keeps no per-statement I/O counters. The estimate is, for each table a statement
# names after FROM or JOIN, its row count times an average row width.
ROW_BYTES = {"raw_orders": 96, "raw_events": 128, "stg_orders": 72, "stg_events": 96}
DEFAULT_ROW_BYTES = 64
_TABLES = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class QueryRecord:
    started_at: float
    query_id: str
    source: str
    duration_ms: float
    rows_read: int
    bytes_read: int


class Warehouse:
    """One connection, recording each statement it runs."""

    def __init__(self, path: str | Path = ":memory:", source: str = "adhoc") -> None:
        self.path = str(path)
        self.source = source
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(QUERY_LOG_DDL)
        self.conn.commit()

    def __enter__(self) -> Warehouse:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def run(
        self, query_id: str, sql: str, params: Sequence = (), source: str | None = None
    ) -> list[tuple]:
        """Run one statement and return its rows."""

        started, clock = time.time(), time.perf_counter()
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        touched = len(rows) if rows else max(cursor.rowcount, 0)
        self._record(started, clock, query_id, source, touched, sql)
        return rows

    def script(self, query_id: str, sql: str, source: str | None = None) -> None:
        """Run a script of several statements, as the transforms are."""

        started, clock = time.time(), time.perf_counter()
        self.conn.executescript(sql)
        self._record(started, clock, query_id, source, 0, sql)

    def many(
        self, query_id: str, sql: str, rows: Iterable[Sequence], source: str | None = None
    ) -> int:
        """Run one statement for each row, as the loader does; return how many rows."""

        batch = list(rows)
        started, clock = time.time(), time.perf_counter()
        self.conn.executemany(sql, batch)
        self._record(started, clock, query_id, source, len(batch), "")
        return len(batch)

    def tables(self) -> list[str]:
        found = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        return [row[0] for row in found]

    def count(self, table: str) -> int:
        """How many rows `table` holds; 0 where there is no such table."""

        if not _NAME.match(table) or table not in self.tables():
            return 0
        return int(self.conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])

    def query_log(self) -> list[QueryRecord]:
        rows = self.conn.execute(
            "SELECT started_at, query_id, source, duration_ms, rows_read, bytes_read"
            " FROM query_log ORDER BY started_at"
        ).fetchall()
        return [QueryRecord(*row) for row in rows]

    def bytes_read(self, sql: str) -> int:
        """The estimated bytes a statement reads: see ROW_BYTES."""

        total = 0
        for table in sorted({name.lower() for name in _TABLES.findall(sql)}):
            total += self.count(table) * ROW_BYTES.get(table, DEFAULT_ROW_BYTES)
        return total

    def _record(
        self,
        started: float,
        clock: float,
        query_id: str,
        source: str | None,
        rows: int,
        sql: str,
    ) -> None:
        duration_ms = (time.perf_counter() - clock) * 1000
        self.conn.execute(
            "INSERT INTO query_log VALUES (?, ?, ?, ?, ?, ?)",
            (started, query_id, source or self.source, duration_ms, rows, self.bytes_read(sql)),
        )
        self.conn.commit()
DPEOF

cat > datapipe/batching.py <<'DPEOF'
"""Splitting a stream of rows into batches for the loader."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class BatchPlan:
    batches: int
    last_batch_rows: int


def chunks(rows: Iterable[T], size: int) -> Iterator[list[T]]:
    """Successive lists of at most `size` rows, in order; the last may be shorter."""

    if size < 1:
        raise ValueError("batch size must be at least 1")
    batch: list[T] = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def plan(total_rows: int, size: int) -> BatchPlan:
    """How many batches `total_rows` rows make at `size` rows a batch."""

    if size < 1:
        raise ValueError("batch size must be at least 1")
    if total_rows <= 0:
        return BatchPlan(0, 0)
    batches = math.ceil(total_rows / size)
    return BatchPlan(batches, total_rows - (batches - 1) * size)
DPEOF

cat > datapipe/loader.py <<'DPEOF'
"""Loading CSV extracts into the raw tables, in batches, with an audit row for each load."""

from __future__ import annotations

import csv
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from datapipe import batching
from datapipe.warehouse import Warehouse

COLUMNS = {
    "orders": ("order_id", "customer_id", "ordered_at", "status", "amount_cents"),
    "events": ("event_id", "user_id", "occurred_at", "kind", "page"),
}
INTEGER_COLUMNS = {"order_id", "customer_id", "amount_cents", "event_id", "user_id"}
DDL = """
CREATE TABLE IF NOT EXISTS raw_orders (
    order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, ordered_at TEXT NOT NULL,
    status TEXT NOT NULL, amount_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS raw_events (
    event_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, occurred_at TEXT NOT NULL,
    kind TEXT NOT NULL, page TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS load_audit (
    table_name TEXT NOT NULL, rows INTEGER NOT NULL, batches INTEGER NOT NULL,
    loaded_at REAL NOT NULL
);
"""
INSERT = {
    "orders": "INSERT OR REPLACE INTO raw_orders VALUES (?, ?, ?, ?, ?)",
    "events": "INSERT OR REPLACE INTO raw_events VALUES (?, ?, ?, ?, ?)",
}


class LoadError(Exception):
    """An extract that cannot be loaded."""


@dataclass(frozen=True)
class LoadResult:
    table: str
    rows: int
    batches: int


def ensure_tables(wh: Warehouse) -> None:
    wh.script("loader_ddl", DDL, source="loader")


def read_csv(path: Path, table: str) -> Iterator[tuple]:
    """The rows of an extract, typed, after checking its header against the table's columns."""

    columns = _columns(table)
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = tuple(next(reader, ()))
        if header != columns:
            raise LoadError(f"{path}: header {header} is not {columns}")
        for number, row in enumerate(reader, start=2):
            if len(row) != len(columns):
                raise LoadError(f"{path}:{number}: {len(row)} fields, expected {len(columns)}")
            yield tuple(_typed(name, value, path, number) for name, value in zip(columns, row))


def load(wh: Warehouse, table: str, rows: Iterable[tuple], batch_size: int) -> LoadResult:
    """Insert `rows` into the raw table in batches of `batch_size`, then audit the load."""

    ensure_tables(wh)
    sql = INSERT[_table(table)]
    total = batches = 0
    for batch in batching.chunks(rows, batch_size):
        total += wh.many(f"load_{table}", sql, batch, source="loader")
        batches += 1
    wh.run(
        "load_audit",
        "INSERT INTO load_audit VALUES (?, ?, ?, ?)",
        (table, total, batches, time.time()),
        source="loader",
    )
    return LoadResult(table, total, batches)


def load_file(wh: Warehouse, path: Path, table: str, batch_size: int) -> LoadResult:
    return load(wh, table, read_csv(path, table), batch_size)


def _table(table: str) -> str:
    if table not in COLUMNS:
        raise LoadError(f"unknown table {table!r}; one of {', '.join(COLUMNS)}")
    return table


def _columns(table: str) -> tuple[str, ...]:
    return COLUMNS[_table(table)]


def _typed(name: str, value: str, path: Path, number: int) -> object:
    if name not in INTEGER_COLUMNS:
        return value
    try:
        return int(value)
    except ValueError:
        raise LoadError(f"{path}:{number}: {name} is not a whole number: {value!r}") from None
DPEOF

cat > datapipe/transforms.py <<'DPEOF'
"""The SQL transforms: one file each under datapipe/sql/, run in dependency order.

Each file starts with header comments that name the table it creates and the transforms it
depends on:

    -- creates: daily_revenue
    -- depends: stg_orders
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from datapipe.warehouse import Warehouse

SQL_DIR = Path(__file__).resolve().parent / "sql"
_HEADER = re.compile(r"^--[ \t]*(creates|depends):[ \t]*(.*)$", re.MULTILINE)


class TransformError(Exception):
    """A transform set that cannot run."""


@dataclass(frozen=True)
class Transform:
    name: str
    creates: str
    depends: tuple[str, ...]
    sql: str


def parse(name: str, sql: str) -> Transform:
    fields: dict[str, str] = {}
    for key, value in _HEADER.findall(sql):
        fields[key] = value.strip()
    if "creates" not in fields:
        raise TransformError(f"{name}: no '-- creates:' header")
    depends = tuple(item.strip() for item in fields.get("depends", "").split(",") if item.strip())
    return Transform(name, fields["creates"], depends, sql)


def discover(directory: Path = SQL_DIR) -> dict[str, Transform]:
    """Every transform under `directory`, by name (the file's stem)."""

    found = {}
    for path in sorted(directory.glob("*.sql")):
        found[path.stem] = parse(path.stem, path.read_text(encoding="utf-8"))
    return found


def order(transforms: dict[str, Transform], wanted: list[str] | None = None) -> list[str]:
    """The names to run, dependencies first; `wanted` limits it to those and what they need."""

    done: list[str] = []
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in done:
            return
        if name not in transforms:
            raise TransformError(f"unknown transform {name!r}")
        if name in visiting:
            raise TransformError(f"dependency cycle through {name!r}")
        visiting.add(name)
        for dependency in transforms[name].depends:
            visit(dependency)
        visiting.discard(name)
        done.append(name)

    for name in wanted if wanted is not None else sorted(transforms):
        visit(name)
    return done


def run(wh: Warehouse, transform: Transform, source: str = "scheduler") -> int:
    """Run one transform; return the rows of the table it creates."""

    wh.script(transform.name, transform.sql, source=source)
    return wh.count(transform.creates)


def run_all(
    wh: Warehouse, wanted: list[str] | None = None, directory: Path = SQL_DIR
) -> dict[str, int]:
    """Run the transforms in order; return the rows each created table holds."""

    transforms = discover(directory)
    return {name: run(wh, transforms[name]) for name in order(transforms, wanted)}
DPEOF

cat > datapipe/sql/stg_orders.sql <<'DPEOF'
-- creates: stg_orders
-- depends:
-- Orders as the reports read them: one row per order, the day it was placed, amounts in cents.
DROP TABLE IF EXISTS stg_orders;
CREATE TABLE stg_orders AS
SELECT
    order_id,
    customer_id,
    date(ordered_at) AS order_day,
    lower(status) AS status,
    amount_cents
FROM raw_orders
WHERE order_id IS NOT NULL;
DPEOF

cat > datapipe/sql/stg_events.sql <<'DPEOF'
-- creates: stg_events
-- depends:
-- Page events with a usable timestamp; bot traffic (kind 'bot') is left out.
DROP TABLE IF EXISTS stg_events;
CREATE TABLE stg_events AS
SELECT
    event_id,
    user_id,
    occurred_at,
    kind,
    page
FROM raw_events
WHERE occurred_at IS NOT NULL
  AND kind <> 'bot';
DPEOF

cat > datapipe/sql/daily_revenue.sql <<'DPEOF'
-- creates: daily_revenue
-- depends: stg_orders
-- Revenue by day. Cancelled and refunded orders do not count (docs/specs/revenue.md).
DROP TABLE IF EXISTS daily_revenue;
CREATE TABLE daily_revenue AS
SELECT
    order_day,
    COUNT(*) AS orders,
    SUM(amount_cents) AS revenue_cents
FROM stg_orders
WHERE status NOT IN ('cancelled', 'refunded')
GROUP BY order_day;
DPEOF

cat > datapipe/sql/customer_ltv.sql <<'DPEOF'
-- creates: customer_ltv
-- depends: stg_orders
-- Lifetime value per customer: what each has paid, over how many orders, first and last day.
DROP TABLE IF EXISTS customer_ltv;
CREATE TABLE customer_ltv AS
SELECT
    customer_id,
    COUNT(*) AS orders,
    SUM(amount_cents) AS paid_cents,
    MIN(order_day) AS first_day,
    MAX(order_day) AS last_day
FROM stg_orders
WHERE status NOT IN ('cancelled', 'refunded')
GROUP BY customer_id;
DPEOF

cat > datapipe/sql/sessionize_events.sql <<'DPEOF'
-- creates: sessions
-- depends: stg_events
-- Sessions: a user's events with no gap longer than 30 minutes. Rebuilt from every event in
-- the lookback window each night.
DROP TABLE IF EXISTS sessions;
CREATE TABLE sessions AS
WITH gaps AS (
    SELECT
        user_id,
        occurred_at,
        (CAST(strftime('%s', occurred_at) AS INTEGER)
            - CAST(strftime('%s', LAG(occurred_at) OVER w) AS INTEGER)) AS gap_seconds
    FROM stg_events
    WINDOW w AS (PARTITION BY user_id ORDER BY occurred_at, event_id)
),
numbered AS (
    SELECT
        user_id,
        occurred_at,
        SUM(CASE WHEN gap_seconds IS NULL OR gap_seconds > 1800 THEN 1 ELSE 0 END)
            OVER (PARTITION BY user_id ORDER BY occurred_at ROWS UNBOUNDED PRECEDING)
            AS session_no
    FROM gaps
)
SELECT
    user_id,
    session_no,
    MIN(occurred_at) AS started_at,
    MAX(occurred_at) AS ended_at,
    COUNT(*) AS events
FROM numbered
GROUP BY user_id, session_no;
DPEOF

cat > datapipe/scheduler.py <<'DPEOF'
"""The scheduler: each job runs once a day at its time, after the jobs it depends on.

A job that fails is retried up to MAX_RETRIES times, RETRY_DELAY_MINUTES apart; after that it
is marked failed for the day and the jobs that depend on it do not run. A new day starts each
job afresh. The schedule is config/schedule.ini.
"""

from __future__ import annotations

import configparser
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from datapipe.config import CONFIG_DIR

MAX_RETRIES = 3
RETRY_DELAY_MINUTES = 10
SCHEDULE = CONFIG_DIR / "schedule.ini"


class ScheduleError(Exception):
    """A schedule that cannot be read."""


@dataclass(frozen=True)
class Job:
    name: str
    at: int  # minutes after midnight
    depends: tuple[str, ...] = ()


@dataclass
class JobState:
    day: str = ""
    attempts: int = 0
    next_try: int = 0
    status: str = "waiting"  # waiting, done, failed


@dataclass(frozen=True)
class Outcome:
    day: str
    minute: int
    job: str
    attempt: int
    ok: bool
    error: str = ""


def parse_time(text: str) -> int:
    """Minutes after midnight of an `HH:MM` time."""

    try:
        hours, minutes = (int(part) for part in text.strip().split(":"))
    except ValueError:
        raise ScheduleError(f"not a time: {text!r}") from None
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        raise ScheduleError(f"not a time: {text!r}")
    return hours * 60 + minutes


def load_schedule(path: Path = SCHEDULE) -> dict[str, Job]:
    parser = configparser.ConfigParser()
    if not parser.read(str(path), encoding="utf-8"):
        raise ScheduleError(f"no schedule at {path}")
    jobs = {}
    for name in parser.sections():
        section = parser[name]
        depends = tuple(d.strip() for d in section.get("depends", "").split(",") if d.strip())
        jobs[name] = Job(name, parse_time(section.get("at", "")), depends)
    for job in jobs.values():
        for dependency in job.depends:
            if dependency not in jobs:
                raise ScheduleError(f"{job.name} depends on unknown job {dependency!r}")
    return jobs


@dataclass
class Scheduler:
    jobs: dict[str, Job]
    runner: Callable[[str], None]
    states: dict[str, JobState] = field(default_factory=dict)

    def state(self, name: str, day: str) -> JobState:
        current = self.states.get(name)
        if current is None or current.day != day:
            current = self.states[name] = JobState(day=day)
        return current

    def due(self, day: str, minute: int) -> list[str]:
        """The jobs that should start now, in name order."""

        ready = []
        for name in sorted(self.jobs):
            job, state = self.jobs[name], self.state(name, day)
            if state.status != "waiting" or minute < job.at or minute < state.next_try:
                continue
            if all(self.state(d, day).status == "done" for d in job.depends):
                ready.append(name)
        return ready

    def tick(self, now: datetime) -> list[Outcome]:
        """Start every due job once; return what happened."""

        day, minute = now.date().isoformat(), now.hour * 60 + now.minute
        outcomes = []
        for name in self.due(day, minute):
            state = self.state(name, day)
            state.attempts += 1
            try:
                self.runner(name)
            except Exception as problem:  # a job's failure is recorded, never raised
                outcomes.append(Outcome(day, minute, name, state.attempts, False, str(problem)))
                if state.attempts > MAX_RETRIES:
                    state.status = "failed"
                else:
                    state.next_try = minute + RETRY_DELAY_MINUTES
                continue
            state.status = "done"
            outcomes.append(Outcome(day, minute, name, state.attempts, True))
        return outcomes


def run_loop(
    scheduler: Scheduler,
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
    ticks: int,
    tick_seconds: float = 60.0,
) -> list[Outcome]:
    """Tick `ticks` times, sleeping `tick_seconds` between ticks, as the service does."""

    outcomes: list[Outcome] = []
    for number in range(ticks):
        outcomes.extend(scheduler.tick(clock()))
        if number + 1 < ticks:
            sleep(tick_seconds)
    return outcomes
DPEOF

cat > datapipe/querystats.py <<'DPEOF'
"""Query statistics: per-query totals from a query log, ranked and exported.

The records come from a warehouse's query_log table (datapipe.warehouse) or from a CSV export
of the production warehouse's statistics with the same columns:

    started_at,query_id,source,duration_ms,rows_read,bytes_read

where started_at is an ISO 8601 time (in the CSV) or a Unix time (in the table).
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from datapipe.warehouse import QueryRecord

SORT_KEYS = ("calls", "bytes", "time")
CSV_COLUMNS = ("started_at", "query_id", "source", "duration_ms", "rows_read", "bytes_read")
_UNITS = ("B", "KB", "MB", "GB", "TB")


@dataclass(frozen=True)
class QueryTotals:
    query_id: str
    source: str
    calls: int
    total_ms: float
    rows_read: int
    bytes_read: int

    @property
    def mean_ms(self) -> float:
        return self.total_ms / self.calls if self.calls else 0.0


def aggregate(records: Iterable[QueryRecord]) -> list[QueryTotals]:
    """One total per query id and source, in query id order."""

    sums: dict[tuple[str, str], list[float]] = {}
    for record in records:
        key = (record.query_id, record.source)
        total = sums.setdefault(key, [0, 0.0, 0, 0])
        total[0] += 1
        total[1] += record.duration_ms
        total[2] += record.rows_read
        total[3] += record.bytes_read
    return [
        QueryTotals(query_id, source, int(t[0]), t[1], int(t[2]), int(t[3]))
        for (query_id, source), t in sorted(sums.items())
    ]


def top(totals: list[QueryTotals], sort: str = "calls", n: int = 10) -> list[QueryTotals]:
    """The `n` largest totals by `sort` (calls, bytes or time), largest first."""

    if sort not in SORT_KEYS:
        raise ValueError(f"sort must be one of {', '.join(SORT_KEYS)}")
    if n < 1:
        raise ValueError("n must be at least 1")
    key = {
        "calls": lambda t: t.calls,
        "bytes": lambda t: t.bytes_read,
        "time": lambda t: t.total_ms,
    }[sort]
    ranked = sorted(totals, key=lambda t: (-key(t), t.query_id))
    return ranked[:n]


def format_bytes(count: float) -> str:
    """A byte count for people: 1536 is '1.5 KB'."""

    value = float(count)
    for unit in _UNITS:
        if abs(value) < 1024 or unit == _UNITS[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {_UNITS[-1]}"


def read_csv(
    path: Path, since: datetime | None = None, until: datetime | None = None
) -> list[QueryRecord]:
    """The records of a CSV export, limited to [since, until) where given."""

    records = []
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError(f"{path}: columns are not {', '.join(CSV_COLUMNS)}")
        for row in reader:
            started = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
            if since is not None and started < since:
                continue
            if until is not None and started >= until:
                continue
            records.append(
                QueryRecord(
                    started.replace(tzinfo=timezone.utc).timestamp(),
                    row["query_id"],
                    row["source"],
                    float(row["duration_ms"]),
                    int(row["rows_read"]),
                    int(row["bytes_read"]),
                )
            )
    return records


def render_table(totals: list[QueryTotals]) -> str:
    """A fixed-width table for a terminal."""

    lines = [f"{'query_id':<28} {'source':<14} {'calls':>7} {'total_ms':>12} {'bytes_read':>11}"]
    for t in totals:
        lines.append(
            f"{t.query_id:<28} {t.source:<14} {t.calls:>7} {t.total_ms:>12.0f}"
            f" {format_bytes(t.bytes_read):>11}"
        )
    return "\n".join(lines)


def to_csv(totals: list[QueryTotals]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["query_id", "source", "calls", "total_ms", "rows_read", "bytes_read"])
    for t in totals:
        writer.writerow(
            [t.query_id, t.source, t.calls, f"{t.total_ms:.1f}", t.rows_read, t.bytes_read]
        )
    return out.getvalue()


def to_json(totals: list[QueryTotals]) -> str:
    return json.dumps([asdict(t) for t in totals], indent=2) + "\n"


FORMATS = {"table": render_table, "csv": to_csv, "json": to_json}
DPEOF

cat > datapipe/health.py <<'DPEOF'
"""The health check: the warehouse answers, and the last load is fresh.

It is meant to be cheap enough to run every minute: one trivial query and one read of the
small load_audit table. It never scans a data table.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from datapipe.warehouse import Warehouse

MAX_AGE_HOURS = 26.0


@dataclass(frozen=True)
class HealthReport:
    ok: bool
    freshness_hours: float | None
    problems: tuple[str, ...]


def check(
    wh: Warehouse, now: float | None = None, max_age_hours: float = MAX_AGE_HOURS
) -> HealthReport:
    now = time.time() if now is None else now
    problems = []
    if wh.run("health_ping", "SELECT 1", source="monitor") != [(1,)]:
        problems.append("the warehouse did not answer SELECT 1")
    freshness = None
    if "load_audit" in wh.tables():
        latest = wh.run(
            "health_freshness", "SELECT MAX(loaded_at) FROM load_audit", source="monitor"
        )[0][0]
        if latest is not None:
            freshness = (now - float(latest)) / 3600
    if freshness is None:
        problems.append("no load has been recorded")
    elif freshness > max_age_hours:
        problems.append(f"the last load is {freshness:.1f} hours old (limit {max_age_hours:g})")
    return HealthReport(not problems, freshness, tuple(problems))
DPEOF

cat > datapipe/capacity.py <<'DPEOF'
"""Capacity checks for an environment, from a dataset profile (docs/specs/capacity.md).

Two checks, each a model of the nightly load with the environment's settings:

- window: the minutes a nightly load of the profile's rows needs, at the configured batch
  size, per-batch overhead and per-row cost, must fit the load window;
- memory: the loader's peak memory, batch size times workers times the profile's average row
  width, must fit the memory budget.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from datapipe.config import ROOT, Settings

PROFILES = ROOT / "data" / "profiles"


class ProfileError(Exception):
    """A dataset profile that cannot be read."""


@dataclass(frozen=True)
class Profile:
    name: str
    rows: int
    avg_row_bytes: int
    max_row_bytes: int


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    value: float
    limit: float
    unit: str

    def line(self) -> str:
        verdict = "ok" if self.ok else "FAILS"
        return f"{self.name}: {self.value:.1f} {self.unit} (limit {self.limit:g}) {verdict}"


def load_profile(name: str, directory: Path = PROFILES) -> Profile:
    path = directory / f"{name}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Profile(
            name, int(data["rows"]), int(data["avg_row_bytes"]), int(data["max_row_bytes"])
        )
    except (OSError, ValueError, KeyError) as problem:
        raise ProfileError(f"cannot read profile {name!r} at {path}: {problem}") from problem


def window_minutes(rows: int, batch_size: int, overhead_s: float, row_cost_ms: float) -> float:
    """Minutes a load of `rows` needs: each batch pays the overhead, each row its cost."""

    batches = math.ceil(rows / batch_size) if rows else 0
    return (batches * overhead_s + rows * row_cost_ms / 1000) / 60


def peak_memory_mb(batch_size: int, workers: int, row_bytes: int) -> float:
    """Peak loader memory: each worker holds one batch of rows."""

    return batch_size * workers * row_bytes / 1_000_000


def check(settings: Settings, directory: Path = PROFILES) -> list[CheckResult]:
    profile = load_profile(settings.profile, directory)
    window = window_minutes(
        profile.rows, settings.batch_size, settings.batch_overhead_s, settings.row_cost_ms
    )
    memory = peak_memory_mb(settings.batch_size, settings.workers, profile.avg_row_bytes)
    return [
        CheckResult(
            "window", window <= settings.window_minutes, window, settings.window_minutes, "min"
        ),
        CheckResult(
            "memory", memory <= settings.memory_budget_mb, memory, settings.memory_budget_mb, "MB"
        ),
    ]
DPEOF

cat > datapipe/cli.py <<'DPEOF'
"""The datapipe command line."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from datapipe import __version__, capacity, config, health, loader, querystats, scheduler
from datapipe import transforms
from datapipe.warehouse import Warehouse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="datapipe", description=__doc__)
    parser.add_argument("--version", action="version", version=f"datapipe {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run the transforms")
    run.add_argument("--env", default="dev", choices=config.ENVIRONMENTS)
    run.add_argument("--only", action="append", help="a transform to run (and what it needs)")

    load = commands.add_parser("load", help="load one CSV extract into a raw table")
    load.add_argument("--env", default="dev", choices=config.ENVIRONMENTS)
    load.add_argument("--table", required=True, choices=sorted(loader.COLUMNS))
    load.add_argument("--file", required=True, type=Path)
    load.add_argument("--batch-size", type=int, help="override the configured batch size")

    backfill = commands.add_parser("backfill", help="load a range of daily extracts")
    backfill.add_argument("--env", default="dev", choices=config.ENVIRONMENTS)
    backfill.add_argument("--table", required=True, choices=sorted(loader.COLUMNS))
    backfill.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    backfill.add_argument("--to", dest="end", required=True, type=date.fromisoformat)
    backfill.add_argument("--extracts", type=Path, default=Path("data/extracts"))

    stats = commands.add_parser("stats", help="query statistics")
    stats_commands = stats.add_subparsers(dest="stats_command", required=True)
    export = stats_commands.add_parser("export", help="rank queries from a query log")
    export.add_argument("--db", type=Path, help="a warehouse file whose query_log to read")
    export.add_argument("--csv", type=Path, help="a CSV export of production statistics")
    export.add_argument("--sort", default="calls", choices=querystats.SORT_KEYS)
    export.add_argument("--top", type=int, default=10)
    export.add_argument("--format", default="table", choices=sorted(querystats.FORMATS))

    check = commands.add_parser("health", help="run the health check")
    check.add_argument("--env", default="dev", choices=config.ENVIRONMENTS)

    cap = commands.add_parser("capacity", help="run the capacity checks")
    cap.add_argument("--env", default="stage", choices=config.ENVIRONMENTS)

    due = commands.add_parser("schedule", help="show which jobs are due at a time")
    due.add_argument("--at", default="03:00")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return HANDLERS[args.command](args)
    except (
        config.ConfigError,
        loader.LoadError,
        transforms.TransformError,
        capacity.ProfileError,
        scheduler.ScheduleError,
        ValueError,
    ) as problem:
        print(f"datapipe: {problem}", file=sys.stderr)
        return 2


def _warehouse(env: str) -> Warehouse:
    return Warehouse(config.load(env).warehouse_path, source="cli")


def _run(args: argparse.Namespace) -> int:
    with _warehouse(args.env) as wh:
        for name, rows in transforms.run_all(wh, args.only).items():
            print(f"{name}: {rows} rows")
    return 0


def _load(args: argparse.Namespace) -> int:
    settings = config.load(args.env)
    with _warehouse(args.env) as wh:
        result = loader.load_file(wh, args.file, args.table, args.batch_size or settings.batch_size)
    print(f"{result.table}: {result.rows} rows in {result.batches} batches")
    return 0


def _backfill(args: argparse.Namespace) -> int:
    if args.end < args.start:
        raise ValueError("--to is before --from")
    settings = config.load(args.env)
    day, files = args.start, []
    while day <= args.end:
        files.append(args.extracts / args.table / f"{day.isoformat()}.csv")
        day += timedelta(days=1)
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise ValueError("missing extracts: " + ", ".join(missing))
    with _warehouse(args.env) as wh:
        for path in files:
            result = loader.load_file(wh, path, args.table, settings.batch_size)
            print(f"{path.name}: {result.rows} rows")
    return 0


def _stats(args: argparse.Namespace) -> int:
    if (args.db is None) == (args.csv is None):
        raise ValueError("give exactly one of --db and --csv")
    if args.db is not None:
        with Warehouse(args.db) as wh:
            records = wh.query_log()
    else:
        records = querystats.read_csv(args.csv)
    ranked = querystats.top(querystats.aggregate(records), args.sort, args.top)
    print(querystats.FORMATS[args.format](ranked))
    return 0


def _health(args: argparse.Namespace) -> int:
    with _warehouse(args.env) as wh:
        report = health.check(wh)
    print("healthy" if report.ok else "unhealthy: " + "; ".join(report.problems))
    return 0 if report.ok else 1


def _capacity(args: argparse.Namespace) -> int:
    settings = config.load(args.env)
    results = capacity.check(settings)
    print(f"capacity of {args.env} on profile {settings.profile}:")
    for result in results:
        print("  " + result.line())
    return 0 if all(result.ok for result in results) else 1


def _schedule(args: argparse.Namespace) -> int:
    jobs = scheduler.load_schedule()
    plan = scheduler.Scheduler(jobs, lambda _name: None)
    minute = scheduler.parse_time(args.at)
    for name in plan.due(datetime.now().date().isoformat(), minute):
        print(name)
    return 0


HANDLERS = {
    "run": _run,
    "load": _load,
    "backfill": _backfill,
    "stats": _stats,
    "health": _health,
    "capacity": _capacity,
    "schedule": _schedule,
}
DPEOF

cat > config/base.ini <<'DPEOF'
# Settings every environment starts from; config/<env>.ini overrides them.
[warehouse]
path = :memory:

[loader]
batch_size = 5000
workers = 4

[capacity]
# The cost model of a nightly load (docs/specs/capacity.md).
batch_overhead_s = 1.2
row_cost_ms = 1.5
window_minutes = 45
memory_budget_mb = 64
profile = reference-2026q3
DPEOF

cat > config/dev.ini <<'DPEOF'
# Local development: an in-memory warehouse, small batches.
[warehouse]
path = :memory:

[loader]
batch_size = 1000
workers = 1
DPEOF

cat > config/stage.ini <<'DPEOF'
# Stage: the reference dataset, at production's per-row cost, on smaller hardware.
[warehouse]
path = /srv/datapipe/stage/warehouse.db

[loader]
batch_size = 5000
workers = 4
DPEOF

cat > config/prod.ini <<'DPEOF'
# Production: larger batches and more workers; sized for the peak-burst profile (C3).
[warehouse]
path = /srv/datapipe/prod/warehouse.db

[loader]
batch_size = 10000
workers = 8

[capacity]
batch_overhead_s = 0.8
row_cost_ms = 1.0
window_minutes = 120
memory_budget_mb = 256
profile = peak-burst
DPEOF

cat > config/schedule.ini <<'DPEOF'
# The nightly schedule (UTC). Each job is a transform under datapipe/sql/.
[stg_orders]
at = 02:00

[stg_events]
at = 02:10

[daily_revenue]
at = 02:30
depends = stg_orders

[sessionize_events]
at = 03:00
depends = stg_events

[customer_ltv]
at = 03:30
depends = stg_orders
DPEOF

cat > data/profiles/reference-2026q3.json <<'DPEOF'
{
  "description": "The reference dataset: a typical night of 2026 Q3, measured on 2026-09-30.",
  "rows": 1200000,
  "avg_row_bytes": 1800,
  "max_row_bytes": 9500
}
DPEOF

cat > data/profiles/peak-burst.json <<'DPEOF'
{
  "description": "Peak burst: three typical nights at once, for the production scale test (C3).",
  "rows": 3600000,
  "avg_row_bytes": 2100,
  "max_row_bytes": 12000
}
DPEOF

python3 -B - <<'DPEOF'
import csv
import random

rng = random.Random(20260930)
statuses = ["paid"] * 17 + ["cancelled", "refunded", "paid"]
with open("data/sample/orders.csv", "w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(["order_id", "customer_id", "ordered_at", "status", "amount_cents"])
    for order_id in range(1, 241):
        day = 1 + order_id % 14
        writer.writerow([
            order_id,
            100 + rng.randrange(40),
            f"2026-09-{day:02d}T{rng.randrange(24):02d}:{rng.randrange(60):02d}:00",
            rng.choice(statuses),
            rng.randrange(500, 25000),
        ])
pages = ["/", "/pricing", "/docs", "/signup", "/blog"]
with open("data/sample/events.csv", "w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(["event_id", "user_id", "occurred_at", "kind", "page"])
    for event_id in range(1, 401):
        minute = rng.randrange(0, 24 * 60)
        writer.writerow([
            event_id,
            500 + rng.randrange(30),
            f"2026-09-03T{minute // 60:02d}:{minute % 60:02d}:00",
            rng.choice(["view"] * 8 + ["click", "bot"]),
            rng.choice(pages),
        ])
DPEOF
