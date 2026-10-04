"""The change, judged through the command line against databases of the probe's own.

probe.py new        a new database: prices go in as 12.50, come out the same, and are
                    stored as integer cents
probe.py existing   a copy of the shop's stock as it was before the change, brought up to
                    date by the workspace's own migrations: every price and quantity
                    survives, now as integer cents, and the value is unchanged
"""

import importlib.util
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "cli_probe", Path(__file__).resolve().parent / "cli_probe.py"
)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit("no cli_probe.py beside this probe")
cli = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cli)

BEFORE = Path(__file__).resolve().parent / "stock-before.db"


def cents_column(database, want):
    """Whether some column of `items`, read by SKU, holds exactly `want` as integers."""
    conn = sqlite3.connect(str(database))
    try:
        cursor = conn.execute("SELECT * FROM items ORDER BY sku")
        names = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
    finally:
        conn.close()
    for index, name in enumerate(names):
        if name in ("sku", "name", "qty"):
            continue
        values = [row[index] for row in rows]
        if all(type(value) is int for value in values) and values == want:
            return True
    return False


def rows(database):
    """Each item's SKU, name and quantity, by SKU."""
    conn = sqlite3.connect(str(database))
    try:
        return conn.execute("SELECT sku, name, qty FROM items ORDER BY sku").fetchall()
    finally:
        conn.close()


def check(database, prices, value):
    status, out, err = cli.run(database, "list")
    got = [price for _sku, price in cli.listed(out)]
    if status != 0 or got != prices:
        raise SystemExit(f"list printed prices {got}, not {prices}: {err.strip()}")
    status, out, err = cli.run(database, "value")
    if status != 0 or out.strip() != value:
        raise SystemExit(f"value printed {out.strip()!r}, not {value!r}: {err.strip()}")
    want = [int(price.replace(".", "")) for price in prices]
    if not cents_column(database, want):
        raise SystemExit(f"no column of items holds the prices as integer cents {want}")


def new(scratch):
    database = cli.fresh(scratch)
    for row in (("A1", "Hammer", "2", "12.50"), ("B2", "Tape", "3", "1.05")):
        status, _out, err = cli.run(database, "add", *row)
        if status != 0:
            raise SystemExit(f"add {' '.join(row)} exited {status}: {err.strip()}")
    check(database, ["12.50", "1.05"], "28.15")


def existing(scratch):
    database = Path(scratch) / "stock.db"
    shutil.copy(BEFORE, database)
    kept = rows(BEFORE)
    status, _out, err = cli.run(database, "migrate")
    if status != 0:
        raise SystemExit(f"migrate on the stock as it was exited {status}: {err.strip()}")
    try:
        after = rows(database)
    except sqlite3.Error as error:
        raise SystemExit(f"the migrated stock has no sku, name and qty to read: {error}") from None
    if after != kept:
        raise SystemExit(f"the migrated stock reads {after}, not {kept}")
    check(database, ["12.50", "3.99", "1.05", "2.35"], "324.00")


with tempfile.TemporaryDirectory() as scratch:
    {"new": new, "existing": existing}[sys.argv[1]](scratch)
print("ok")
