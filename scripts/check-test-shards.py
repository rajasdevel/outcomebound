#!/usr/bin/env python3
"""Guard: CI's shards of the suite are disjoint and together are the whole suite.

CI runs the suite in several jobs; a job sets OUTCOMEBOUND_TEST_SHARD to "<index>/<count>" and
tests/conftest.py keeps the tests whose id falls in that part. A test whose id changes from one
run to the next (an id that holds an address, a time or a temporary path) would fall in two parts
or in none, and no job would say so. This script compares one unsharded collection with the
ids selected inside two xdist workers for each shard, for each count named. The observer stops
xdist before it schedules tests. Missing or repeated ids, empty selections and workers that
disagree fail the check. Collecting runs no test.

Usage: python3 scripts/check-test-shards.py COUNT [COUNT ...]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SHARD_VARIABLE = "OUTCOMEBOUND_TEST_SHARD"


def collect(shard: str | None) -> list[str]:
    """One unsharded collection, or the ids xdist's workers actually select for a shard."""

    env = {key: value for key, value in os.environ.items() if key != SHARD_VARIABLE}
    root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (root, env.get("PYTHONPATH"))))
    if shard:
        env[SHARD_VARIABLE] = shard
    command = [sys.executable, "-m", "pytest", "-q", "-o", "addopts=", "-p", "no:cacheprovider"]
    with tempfile.TemporaryDirectory(prefix="outcomebound-shards-") as directory:
        report = Path(directory) / "workers.json"
        if shard:
            # pytest's --collect-only bypasses xdist. This plugin receives the worker ids
            # through xdist's collection event and exits before any test is scheduled.
            command += ["-n", "2", "-p", "tests.shard_collection"]
            env["OUTCOMEBOUND_SHARD_REPORT"] = str(report)
        else:
            command += ["--collect-only", "-n", "0"]
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
            encoding="utf-8",
        )
        if done.returncode != 0:
            sys.stderr.write(done.stdout[-4000:] + done.stderr[-4000:])
            raise SystemExit(
                f"check-test-shards: collecting the tests failed (exit {done.returncode})"
            )
        if not shard:
            return [
                line
                for line in done.stdout.splitlines()
                if "::" in line and not line.startswith(" ")
            ]
        if not report.is_file():
            raise SystemExit(f"check-test-shards: shard {shard}: no worker collection report")
        workers = json.loads(report.read_text(encoding="utf-8"))
        if set(workers) != {"gw0", "gw1"}:
            raise SystemExit(f"check-test-shards: shard {shard}: expected two worker collections")
        if workers["gw0"] != workers["gw1"]:
            raise SystemExit(
                f"check-test-shards: shard {shard}: workers selected different test ids"
            )
        return workers["gw0"]


def problems(whole: list[str], parts: list[list[str]]) -> list[str]:
    """What is wrong with this split of the suite into parts; empty when it is right."""

    found: list[str] = []
    if not whole:
        found.append("the suite is empty")
    if len(set(whole)) != len(whole):
        found.append("the suite lists a test id twice, so a part cannot tell the two apart")
    expected = set(whole)
    seen: dict[str, int] = {}
    for index, part in enumerate(parts, start=1):
        if not part:
            found.append(f"part {index} is empty")
        for test in part:
            if test in seen:
                found.append(f"in parts {seen[test]} and {index}: {test}")
            seen[test] = index
    found.extend(f"in no part: {test}" for test in sorted(expected - set(seen)))
    found.extend(f"in a part, not in the suite: {test}" for test in sorted(set(seen) - expected))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("counts", nargs="+", type=int, help="shard counts to check, such as 3 2")
    counts = parser.parse_args(argv).counts
    if any(count < 1 for count in counts):
        parser.error("a shard count is 1 or more")
    whole = collect(None)
    failed = False
    for count in counts:
        parts = [collect(f"{index}/{count}") for index in range(1, count + 1)]
        wrong = problems(whole, parts)
        sizes = ", ".join(str(len(part)) for part in parts)
        if wrong:
            failed = True
            print(f"{count} shards of {len(whole)} tests: WRONG ({sizes})")
            for line in wrong[:20]:
                print(f"  {line}")
        else:
            print(f"{count} shards of {len(whole)} tests: disjoint and whole ({sizes})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
