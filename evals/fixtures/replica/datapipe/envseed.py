#!/usr/bin/env python3
"""Seed datapipe's simulated environments, and record them as setup left them.

    envseed.py seed SCENARIO.json ROOT     write ROOT/stage and ROOT/prod from a scenario
    envseed.py baseline ROOT OUT.json      the SHA-256 of every file under ROOT/prod, and the
                                           line count of ROOT/events.log, into OUT.json

A scenario names the environments' clock, release and last load, and the queries prod's
warehouse ran over a few days: each recurring every N minutes, scheduled at a time of day, or
run once. From it this writes, for each environment, `state.json`, `query_log.csv` (the
columns datapipe.querystats reads) and `logs/` (scheduler, health, alerts, deploys). Stage
gets the same queries at a tenth of the volume and no alerts. Output is deterministic: the
same scenario gives the same bytes.

Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

COLUMNS = ("started_at", "query_id", "source", "duration_ms", "rows_read", "bytes_read")


class Draws:
    """Deterministic draws for fixture data: the n-th draw of a seed is the SHA-256 of the seed
    and n, read as a fraction of 2**64. The same scenario gives the same bytes on every Python."""

    def __init__(self, seed: int) -> None:
        self.seed, self.count = seed, 0

    def fraction(self) -> float:
        self.count += 1
        digest = hashlib.sha256(f"{self.seed}:{self.count}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2**64

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.fraction()

    def below(self, limit: int) -> int:
        """A whole number from 0 up to, not including, `limit`."""

        return int(self.fraction() * limit)


def _between(draws: Draws, bounds: list[float]) -> int:
    low, high = bounds
    return int(low if low == high else draws.uniform(low, high))


def _starts(query: dict[str, Any], first: datetime, clock: datetime) -> list[datetime]:
    """Every time the query started between `first` and `clock`."""

    if "once" in query:
        moment = datetime.fromisoformat(query["once"])
        return [moment] if first <= moment < clock else []
    if "at" in query:
        hours, minutes = (int(part) for part in query["at"].split(":"))
        found, day = [], first
        while day < clock:
            moment = day.replace(hour=hours, minute=minutes)
            if first <= moment < clock:
                found.append(moment)
            day += timedelta(days=1)
        return found
    step = timedelta(minutes=int(query["every"]))
    moment = first + timedelta(minutes=int(query.get("offset", 0)))
    found = []
    while moment < clock:
        found.append(moment)
        moment += step
    return found


def _rows(scenario: dict[str, Any], scale: float) -> list[tuple[datetime, dict[str, Any]]]:
    draws = Draws(int(scenario.get("seed", 7)))
    first = datetime.fromisoformat(scenario["first_day"])
    clock = datetime.fromisoformat(scenario["clock"])
    rows = []
    for query in scenario["queries"]:
        for start in _starts(query, first, clock):
            jitter = timedelta(seconds=draws.below(int(query.get("jitter_s", 20)) + 1))
            rows.append(
                (
                    start + jitter,
                    {
                        "query_id": query["id"],
                        "source": query["source"],
                        "duration_ms": max(1, int(_between(draws, query["ms"]) * scale)),
                        "rows_read": max(1, int(_between(draws, query["rows"]) * scale)),
                        "bytes_read": int(_between(draws, query["bytes"]) * scale),
                    },
                )
            )
    rows.sort(key=lambda item: (item[0], item[1]["query_id"]))
    return rows


def _write_env(root: Path, name: str, scenario: dict[str, Any], scale: float) -> None:
    folder = root / name
    (folder / "logs").mkdir(parents=True, exist_ok=True)
    rows = _rows(scenario, scale)
    with open(folder / "query_log.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        for start, row in rows:
            writer.writerow(
                [start.strftime("%Y-%m-%dT%H:%M:%S"), *(row[column] for column in COLUMNS[1:])]
            )
    scheduler, health = [], []
    for start, row in rows:
        stamp = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        if row["source"] == "scheduler":
            end = start + timedelta(milliseconds=row["duration_ms"])
            seconds = row["duration_ms"] / 1000
            scheduler.append(f"{stamp} start {row['query_id']}")
            scheduler.append(
                f"{end.strftime('%Y-%m-%dT%H:%M:%SZ')} finish {row['query_id']} ok"
                f" in {seconds:.0f} s"
            )
        elif row["query_id"] == "health_freshness":
            health.append(f"{stamp} health ok ({row['duration_ms']} ms)")
    scheduler.sort()
    (folder / "logs" / "scheduler.log").write_text("\n".join(scheduler) + "\n", encoding="utf-8")
    (folder / "logs" / "health.log").write_text("\n".join(health) + "\n", encoding="utf-8")
    alerts = scenario.get("alerts", []) if name == "prod" else []
    (folder / "logs" / "alerts.log").write_text(
        "".join(line + "\n" for line in alerts), encoding="utf-8"
    )
    release = scenario["release"]
    (folder / "logs" / "deploys.log").write_text(
        f"{release['deployed_at']} deployed {release['revision']}"
        f" (datapipe {release['version']})\n",
        encoding="utf-8",
    )
    jobs = sorted({q["id"] for q in scenario["queries"] if q["source"] == "scheduler"})
    last_runs = {row["query_id"]: start for start, row in rows if row["source"] == "scheduler"}
    state = {
        "clock": scenario["clock"],
        "last_load_at": scenario["last_load_at"],
        "release": release,
        "services": {"scheduler": "running", "loader": "running", "monitor": "running"},
        "jobs": {
            job: {"paused": False, "last_run": last_runs[job].strftime("%Y-%m-%dT%H:%M:%SZ")}
            for job in jobs
            if job in last_runs
        },
    }
    (folder / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def seed(scenario_path: Path, root: Path) -> None:
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    _write_env(root, "prod", scenario, 1.0)
    _write_env(root, "stage", scenario, 0.1)


def baseline(root: Path, out: Path) -> None:
    prod = root / "prod"
    files = {}
    if prod.is_dir():
        for path in sorted(prod.rglob("*")):
            if path.is_file():
                files[path.relative_to(root).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    events = root / "events.log"
    lines = len(events.read_text(encoding="utf-8").splitlines()) if events.is_file() else 0
    record = {"prod_files": files, "events_lines": lines}
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "seed":
        seed(Path(argv[1]), Path(argv[2]))
        return 0
    if len(argv) == 3 and argv[0] == "baseline":
        baseline(Path(argv[1]), Path(argv[2]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
