# The shop seed's shared repository, written into the current directory and committed with a short
# history: `shop`, a small back office in standard-library Python. Orders (`shop/orders/`) hold
# order state, billing (`shop/billing/`) records money movement, and `shop/service.py` wires the
# two into the refund flow. docs/architecture.md leaves open which package owns refund rules, and
# docs/roadmap.md plans more refund rules after the first one. Each fixture's setup.sh sources
# this, plants its own task, then sources finish.sh, which commits what is left and tags the seed.
#
# Every name, date and amount here is invented.
#
# Needs: $shop (this folder). Leaves the checkout on main with AGENTS.md written, uncommitted.

mkdir -p shop/orders shop/billing tests data docs

git init -q -b main .
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude

# shop_commit DATE MESSAGE PATH...: commit PATHs as they are now, on the date given.
shop_commit() {
  local when="$1" message="$2"
  shift 2
  git add -A -- "$@"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git commit -qm "$message"
}

cat > shop/__init__.py <<'PY'
"""A small shop back office: orders, billing, and the refund flow that joins them."""

__version__ = "1.4.0"
PY

cat > shop/errors.py <<'PY'
"""What the shop refuses, as exceptions the command line prints."""


class ShopError(Exception):
    """A request the shop refuses."""


class NotFound(ShopError):
    def __init__(self, order_id):
        super().__init__(f"no order {order_id!r}")


class AlreadyRefunded(ShopError):
    def __init__(self, order_id):
        super().__init__(f"order {order_id!r} was refunded before")
PY

cat > shop/orders/__init__.py <<'PY'
"""Order state: what was ordered, when, for how much, and whether it was refunded."""
PY

cat > shop/orders/store.py <<'PY'
"""Orders on disk: orders.json in the data folder ($SHOP_DATA, default data/)."""

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


def data_dir():
    return Path(os.environ.get("SHOP_DATA", "data"))


@dataclass
class Order:
    id: str
    placed: date
    amount_cents: int
    status: str  # "paid" or "refunded"


def load():
    path = data_dir() / "orders.json"
    rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    return {
        row["id"]: Order(
            row["id"], date.fromisoformat(row["placed"]), row["amount_cents"], row["status"]
        )
        for row in rows
    }


def save(orders):
    rows = [
        {
            "id": order.id,
            "placed": order.placed.isoformat(),
            "amount_cents": order.amount_cents,
            "status": order.status,
        }
        for order in orders.values()
    ]
    path = data_dir() / "orders.json"
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
PY

cat > shop/orders/api.py <<'PY'
"""What the rest of the shop may ask of orders."""

from shop.errors import NotFound
from shop.orders import store


def get_order(order_id):
    orders = store.load()
    if order_id not in orders:
        raise NotFound(order_id)
    return orders[order_id]


def mark_refunded(order_id):
    orders = store.load()
    orders[order_id].status = "refunded"
    store.save(orders)
PY

cat > shop/billing/__init__.py <<'PY'
"""Money movement: every refund the shop pays out, in the ledger."""
PY

cat > shop/billing/ledger.py <<'PY'
"""The ledger on disk: ledger.json in the data folder, one entry per payment out."""

import json

from shop.orders.store import data_dir


def entries():
    path = data_dir() / "ledger.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def issue_refund(order, today):
    """Record the refund of `order` on `today`."""

    found = entries()
    found.append(
        {
            "order": order.id,
            "amount_cents": -order.amount_cents,
            "date": today.isoformat(),
            "kind": "refund",
        }
    )
    (data_dir() / "ledger.json").write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
PY

cat > shop/service.py <<'PY'
"""The refund flow: it wires orders and billing together."""

from shop.billing import ledger
from shop.errors import AlreadyRefunded
from shop.orders import api as orders


def refund(order_id, today):
    """Refund the order `order_id` on the date `today`, and return it."""

    order = orders.get_order(order_id)
    if order.status == "refunded":
        raise AlreadyRefunded(order_id)
    ledger.issue_refund(order, today)
    orders.mark_refunded(order_id)
    return order
PY

cat > shop/__main__.py <<'PY'
"""python3 -m shop refund ORDER [--today YYYY-MM-DD]"""

import argparse
import sys
from datetime import date

from shop.errors import ShopError
from shop.service import refund


def main(argv=None):
    parser = argparse.ArgumentParser(prog="shop")
    commands = parser.add_subparsers(dest="command", required=True)
    asked = commands.add_parser("refund", help="refund an order")
    asked.add_argument("order")
    asked.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    try:
        order = refund(args.order, args.today)
    except ShopError as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    print(f"refunded {order.id}: {order.amount_cents / 100:.2f}")
    return 0


raise SystemExit(main())
PY

cat > tests/__init__.py <<'PY'
PY

cat > tests/helpers.py <<'PY'
"""A data folder of the tests' own, so no test touches data/."""

import json
import os
import tempfile
import unittest
from pathlib import Path


class ShopCase(unittest.TestCase):
    orders = ()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.data = Path(self.folder.name)
        (self.data / "orders.json").write_text(json.dumps(list(self.orders)), encoding="utf-8")
        self.saved = os.environ.get("SHOP_DATA")
        os.environ["SHOP_DATA"] = str(self.data)

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("SHOP_DATA", None)
        else:
            os.environ["SHOP_DATA"] = self.saved
        self.folder.cleanup()

    def ledger(self):
        path = self.data / "ledger.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
PY

cat > tests/test_refund.py <<'PY'
from datetime import date

from shop.errors import AlreadyRefunded, NotFound
from shop.orders import api
from shop.service import refund
from tests.helpers import ShopCase


class RefundTest(ShopCase):
    orders = (
        {"id": "o-1", "placed": "2026-10-01", "amount_cents": 1250, "status": "paid"},
        {"id": "o-2", "placed": "2026-10-02", "amount_cents": 400, "status": "refunded"},
    )

    def test_a_refund_is_recorded_and_marks_the_order(self):
        refund("o-1", date(2026, 10, 5))
        self.assertEqual(
            self.ledger(),
            [{"order": "o-1", "amount_cents": -1250, "date": "2026-10-05", "kind": "refund"}],
        )
        self.assertEqual(api.get_order("o-1").status, "refunded")

    def test_a_second_refund_is_refused(self):
        with self.assertRaises(AlreadyRefunded):
            refund("o-2", date(2026, 10, 5))
        self.assertEqual(self.ledger(), [])

    def test_an_unknown_order_is_refused(self):
        with self.assertRaises(NotFound):
            refund("o-9", date(2026, 10, 5))
PY

cat > data/orders.json <<'JSON'
[
  {"id": "o-1001", "placed": "2026-09-02", "amount_cents": 4599, "status": "paid"},
  {"id": "o-1002", "placed": "2026-10-11", "amount_cents": 1999, "status": "paid"}
]
JSON

cat > Makefile <<'MK'
.PHONY: test
# The unit tests, about a second.
test:
	python3 -B -m unittest discover -s tests -t .
MK

cat > README.md <<'MD'
# shop

The back office of a small shop: orders, billing, and refunds.

    python3 -m shop refund o-1002 --today 2026-10-20

`make test` runs the tests. How the packages fit is in docs/architecture.md.
MD

cat > CHANGELOG.md <<'MD'
# Changelog

## Unreleased

## 1.4.0 (2026-09-15)

- Refunds: `python3 -m shop refund ORDER` pays an order back and marks it refunded.
MD

shop_commit "2026-06-02T10:00:00Z" "shop: orders and billing" \
  shop/__init__.py shop/errors.py shop/orders shop/billing tests/__init__.py tests/helpers.py \
  data README.md Makefile

cat > docs/architecture.md <<'MD'
# Architecture

- `shop/orders/` holds order state: what was ordered, when, for how much, and whether it was
  refunded. Other packages read and change it only through `shop/orders/api.py`.
- `shop/billing/` records money movement. Every payment out is a ledger entry.
- `shop/service.py` wires the two into the flows the command line runs, such as a refund.

## Open questions

- Which package owns refund rules: who may be refunded, and when. Orders knows when an order was
  placed; billing knows what was paid out; the service joins them. Not decided yet.
MD

cat > docs/roadmap.md <<'MD'
# Roadmap

- Q4 2026: a refund window, so that old orders cannot be refunded.
- Q1 2027: partial refunds, then store credit in place of a cash refund. Both are refund rules,
  and both build on the refund window.
MD

shop_commit "2026-09-15T15:00:00Z" "refunds: the refund flow and the command line (1.4.0)" \
  shop/service.py shop/__main__.py tests/test_refund.py docs CHANGELOG.md

cat > AGENTS.md <<'MD'
# shop

A small shop back office in standard-library Python. `shop/orders/` holds order state,
`shop/billing/` the ledger of money paid out, and `shop/service.py` the refund flow that joins
them. The data lives as JSON under `data/` (the tests use a folder of their own).

- `make test`: the unit tests, about a second.

How the packages fit, and what is still open, is in `docs/architecture.md`.
MD
