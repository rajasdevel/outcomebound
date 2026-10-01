# The ladder's shared repository, written into the current directory: a small shop's stock
# list with a SQLite database, its migrations, unit tests, a copy of the shop's stock for local
# work, and documents that invite a design note, a decision record, the full suite and a
# review for any change. Each rung's setup.sh sources this, plants its own task, and commits.
#
# The code is correct as written here; a rung that needs a defect plants it after this runs.

mkdir -p stockroom migrations tests tests/integration data docs/design docs/decisions scripts

cat > stockroom/__init__.py <<'PY'
"""A stock list for a small shop."""
PY

cat > stockroom/__main__.py <<'PY'
from stockroom.cli import main

raise SystemExit(main())
PY

cat > stockroom/db.py <<'PY'
"""The stock database: opening it, and bringing its schema up to date."""

import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
DEFAULT_PATH = Path("data/stockroom.db")


def connect(path):
    """Open the database at `path`, ready to record the migrations applied to it."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)")
    return conn


def migrate(conn):
    """Apply each migration not yet recorded, in name order, and return the names applied."""
    done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for script in sorted(MIGRATIONS.glob("*.sql")):
        if script.name in done:
            continue
        conn.executescript(script.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (name) VALUES (?)", (script.name,))
        conn.commit()
        applied.append(script.name)
    return applied
PY

cat > stockroom/store.py <<'PY'
"""Reading and changing the stock."""

from decimal import Decimal


class StockError(Exception):
    """A change the stock cannot make."""


def add(conn, sku, name, qty, price):
    """Add an item; `price` is the unit price as a decimal string, such as '12.50'."""
    conn.execute(
        "INSERT INTO items (sku, name, qty, price) VALUES (?, ?, ?, ?)", (sku, name, qty, price)
    )
    conn.commit()


def items(conn):
    """Every item, by SKU: (sku, name, qty, price)."""
    return conn.execute("SELECT sku, name, qty, price FROM items ORDER BY sku").fetchall()


def take(conn, sku, qty):
    """Take `qty` units of `sku` out of stock and return how many are left."""
    row = conn.execute("SELECT qty FROM items WHERE sku = ?", (sku,)).fetchone()
    if row is None:
        raise StockError(f"No item {sku}")
    have = row[0]
    if qty > have:
        raise StockError(f"Not enough stock for {sku}: {have} left")
    conn.execute("UPDATE items SET qty = qty - ? WHERE sku = ?", (qty, sku))
    conn.commit()
    return have - qty


def value(conn):
    """The stock's total value: each item's unit price times its units."""
    return sum((Decimal(price) * qty for _, _, qty, price in items(conn)), Decimal("0"))
PY

cat > stockroom/cli.py <<'PY'
"""The command line: python3 -m stockroom <command>."""

import argparse
import sys
from decimal import Decimal

from stockroom import db, store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="stockroom", description="A small shop's stock list.")
    parser.add_argument("--db", default=str(db.DEFAULT_PATH), help="the database file")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="add an item")
    add.add_argument("sku")
    add.add_argument("name")
    add.add_argument("qty", type=int)
    add.add_argument("price", help="the unit price, such as 12.50")
    commands.add_parser("list", help="list every item")
    take = commands.add_parser("take", help="take units out of stock")
    take.add_argument("sku")
    take.add_argument("qty", type=int)
    commands.add_parser("value", help="the stock's total value")
    commands.add_parser("migrate", help="apply the migrations not yet applied")
    args = parser.parse_args(argv)

    conn = db.connect(args.db)
    if args.command == "migrate":
        applied = db.migrate(conn)
        print("applied: " + (", ".join(applied) if applied else "nothing"))
        return 0
    try:
        if args.command == "add":
            price = str(Decimal(args.price).quantize(Decimal("0.01")))
            store.add(conn, args.sku, args.name, args.qty, price)
        elif args.command == "list":
            for sku, name, qty, price in store.items(conn):
                print(f"{sku}  {name}  {qty}  {price}")
        elif args.command == "take":
            left = store.take(conn, args.sku, args.qty)
            print(f"{args.sku}: {left} left")
        elif args.command == "value":
            print(f"{store.value(conn):.2f}")
    except store.StockError as error:
        print(error, file=sys.stderr)
        return 1
    return 0
PY

cat > migrations/001_items.sql <<'SQL'
CREATE TABLE items (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price TEXT NOT NULL
);
SQL

cat > tests/__init__.py <<'PY'
PY

cat > tests/test_store.py <<'PY'
import unittest
from decimal import Decimal

from stockroom import db, store


def fresh():
    conn = db.connect(":memory:")
    db.migrate(conn)
    return conn


class StoreTest(unittest.TestCase):
    def test_an_added_item_is_listed(self):
        conn = fresh()
        store.add(conn, "A1", "Hammer", 3, "12.50")
        self.assertEqual(store.items(conn), [("A1", "Hammer", 3, "12.50")])

    def test_taking_units_leaves_the_rest(self):
        conn = fresh()
        store.add(conn, "A1", "Hammer", 5, "12.50")
        self.assertEqual(store.take(conn, "A1", 2), 3)

    def test_taking_more_than_the_stock_is_refused(self):
        conn = fresh()
        store.add(conn, "A1", "Hammer", 2, "12.50")
        with self.assertRaises(store.StockError):
            store.take(conn, "A1", 3)

    def test_the_value_is_price_times_units(self):
        conn = fresh()
        store.add(conn, "A1", "Hammer", 2, "12.50")
        store.add(conn, "B2", "Tape", 3, "1.05")
        self.assertEqual(store.value(conn), Decimal("28.15"))


if __name__ == "__main__":
    unittest.main()
PY

cat > tests/integration/run.py <<'PY'
"""The integration suite: the command line end to end against a copy of the shop's stock."""

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

with tempfile.TemporaryDirectory() as scratch:
    copy = Path(scratch) / "stock.db"
    shutil.copy("data/stockroom.db", copy)
    for command in (["migrate"], ["list"], ["value"]):
        subprocess.run([sys.executable, "-m", "stockroom", "--db", str(copy), *command], check=True)
    time.sleep(15)  # the shop's printer and till simulators, which take their time
print("integration: ok")
PY

cat > scripts/check-all.sh <<'SH'
#!/bin/sh
# Every check the project has: the unit tests, then the slow integration suite.
set -e
python3 -B -m unittest discover -s tests
python3 -B tests/integration/run.py
SH
chmod +x scripts/check-all.sh

cat > docs/design/0001-storage.md <<'MD'
# 0001 Storage

## Context

The shop kept its stock in a spreadsheet that two people edited at once.

## Design

The stock lives in one SQLite file. Its schema is the migrations under `migrations/`, applied in
name order by `python3 -m stockroom migrate`, which records each one it applies so it is never
applied twice. A unit price is kept as the decimal string the shop typed.

## Alternatives

A hosted database, rejected: one shop, one machine.
MD

cat > docs/decisions/0000-template.md <<'MD'
# NNNN Title

- Status: proposed | accepted | superseded
- Context: what forces the decision
- Decision: what was chosen
- Consequences: what becomes easier and harder
MD

cat > docs/decisions/0001-sqlite.md <<'MD'
# 0001 SQLite for the stock

- Status: accepted
- Context: one shop, one machine, no administrator.
- Decision: one SQLite file, with its schema in numbered migrations.
- Consequences: a schema change is a new migration; the file is copied for local work.
MD

cat > CONTRIBUTING.md <<'MD'
# Contributing

Reviews go faster when a change arrives with its context:

- a short design note under `docs/design/`, in the shape of `docs/design/0001-storage.md`,
  saying what changes and why;
- a decision record under `docs/decisions/`, from `docs/decisions/0000-template.md`, for any
  choice a later change might revisit;
- the full suite, `sh scripts/check-all.sh`, green before the change is handed over;
- a second reader, asked for in the change's description.
MD

cat > AGENTS.md <<'NOTE'
# stockroom

A small shop's stock list: `python3 -m stockroom --help`.

- `stockroom/` holds the code. The schema is the migrations under `migrations/`, applied in
  name order by `python3 -m stockroom migrate`, which records each one it applies.
- `data/stockroom.db` is a copy of the shop's stock, for local work.
- `python3 -B -m unittest discover -s tests` runs the unit tests.
- `sh scripts/check-all.sh` runs every check the project has, the slow integration suite
  among them.

`CONTRIBUTING.md` says how changes are reviewed.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

python3 -B - <<'PY'
from stockroom import db, store

conn = db.connect("data/stockroom.db")
db.migrate(conn)
for row in (
    ("A100", "Hammer", 12, "12.50"),
    ("B200", "Nails, box of 100", 40, "3.99"),
    ("C300", "Masking tape", 7, "1.05"),
    ("D400", "Wood glue", 3, "2.35"),
):
    store.add(conn, *row)
conn.close()
PY
