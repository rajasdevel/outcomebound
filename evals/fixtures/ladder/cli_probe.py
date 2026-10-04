"""The shared half of each rung's probe: the workspace's command line, run against a
database file of the probe's own, never one the model can reach."""

import subprocess
import sys
from pathlib import Path


def run(database, *arguments):
    """Exit status, stdout and stderr of `python3 -m stockroom --db <database> ...`."""
    done = subprocess.run(
        [sys.executable, "-B", "-m", "stockroom", "--db", str(database), *arguments],
        capture_output=True,
        text=True,
        cwd=str(Path.cwd()),
        timeout=60,
    )
    return done.returncode, done.stdout, done.stderr


def listed(output):
    """Each listed line as (sku, price): the first word and the last."""
    rows = []
    for line in output.splitlines():
        words = line.split()
        if words:
            rows.append((words[0], words[-1]))
    return rows


def fresh(scratch):
    """A new database file under `scratch`, with every migration applied."""
    database = Path(scratch) / "probe.db"
    status, out, err = run(database, "migrate")
    if status != 0:
        raise SystemExit(f"migrate on a new database exited {status}: {err.strip() or out.strip()}")
    return database
