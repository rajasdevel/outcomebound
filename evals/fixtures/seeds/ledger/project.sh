# The ledger seed's project files, written into the current directory in their final form:
# `ledger`, a small money service in standard-library Python. Accounts and a journal kept as JSON
# under data/, one shared `_debit` that `transfer`, `withdraw` and the monthly fee in `fees.py`
# all go through, a command line, fast unit tests (tests/unit) and a slow integration suite
# (tests/integration, about a minute, logged in .runs/integration.log), a decision log with one
# reverted default, a CONTRIBUTING.md that asks for a design note, a changelog entry and the full
# suite on every change, and a ticket folder. base.sh sources this, then builds the history.

mkdir -p ledger tests/unit tests/integration data docs/tickets

cat > ledger/__init__.py <<'PY'
"""A small money service: accounts, postings between them, and a command line."""

__version__ = "0.9.0"
PY

cat > ledger/__main__.py <<'PY'
from ledger.cli import main

raise SystemExit(main())
PY

cat > ledger/errors.py <<'PY'
"""What the ledger refuses, as exceptions the command line prints."""


class LedgerError(Exception):
    """A request the ledger refuses."""


class UnknownAccount(LedgerError):
    def __init__(self, account_id):
        super().__init__(f"no account {account_id!r}")


class FrozenAccount(LedgerError):
    def __init__(self, account_id):
        super().__init__(f"account {account_id!r} is frozen")


class InsufficientFunds(LedgerError):
    def __init__(self, account_id):
        super().__init__(f"account {account_id!r} has too little money for that")
PY

cat > ledger/money.py <<'PY'
"""Amounts: text such as "12.30" comes in, and the ledger holds whole cents (LD-1)."""

from decimal import Decimal, InvalidOperation

from ledger.errors import LedgerError


def to_cents(amount):
    """The whole cents of `amount`, text with at most two decimal places ("12.3", "0.29")."""
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        raise LedgerError(f"not an amount: {amount!r}") from None
    cents = value * 100
    if not cents.is_finite() or cents != cents.to_integral_value():
        raise LedgerError(f"not an amount in whole cents: {amount!r}")
    return int(cents)
PY

cat > ledger/display.py <<'PY'
"""How amounts look to people and to other systems (LD-3): everything that prints or writes an
amount goes through `format_amount`."""


def format_amount(cents):
    """`cents` as text with two decimal places: 1234 is "12.34", 5 is "0.05"."""
    sign = "-" if cents < 0 else ""
    units, rest = divmod(abs(cents), 100)
    return f"{sign}{units}.{rest:02d}"
PY

cat > ledger/accounts.py <<'PY'
"""Accounts and the book that holds them, kept as JSON files in a data folder."""

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from ledger.errors import LedgerError, UnknownAccount


@dataclass
class Account:
    id: str
    owner: str
    currency: str = "EUR"
    balance: int = 0  # whole cents
    limit: int = 0  # the overdraft allowed, whole cents
    frozen: bool = False


@dataclass
class Book:
    accounts: dict = field(default_factory=dict)
    journal: list = field(default_factory=list)

    def get(self, account_id):
        try:
            return self.accounts[account_id]
        except KeyError:
            raise UnknownAccount(account_id) from None

    def add(self, account):
        if account.id in self.accounts:
            raise LedgerError(f"account {account.id!r} exists")
        self.accounts[account.id] = account
        return account

    def post(self, day, account_id, cents, memo):
        self.journal.append({"day": day, "account": account_id, "cents": cents, "memo": memo})


def load_book(folder="data"):
    """The book kept in `folder`: accounts.json, and journal.jsonl where there is one."""
    folder = Path(folder)
    known = {f.name for f in fields(Account)}
    book = Book()
    for record in json.loads((folder / "accounts.json").read_text(encoding="utf-8")):
        book.add(Account(**{key: value for key, value in record.items() if key in known}))
    journal = folder / "journal.jsonl"
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            if line.strip():
                book.journal.append(json.loads(line))
    return book


def save_book(book, folder="data"):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    records = [asdict(account) for account in book.accounts.values()]
    (folder / "accounts.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    lines = "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in book.journal)
    (folder / "journal.jsonl").write_text(lines, encoding="utf-8")
PY

cat > ledger/ops.py <<'PY'
"""Postings. Every movement of money out of an account goes through `_debit`."""

import datetime

from ledger.errors import FrozenAccount, InsufficientFunds, LedgerError
from ledger.money import to_cents


def _today():
    return datetime.date.today().isoformat()


def _debit(book, account_id, amount, day, memo):
    """Take `amount` (text, such as "12.30") from the account, within its overdraft limit.
    Returns the whole cents taken."""
    account = book.get(account_id)
    cents = to_cents(amount)
    if cents <= 0:
        raise LedgerError(f"an amount must be above zero: {amount!r}")
    if account.frozen:
        raise FrozenAccount(account_id)
    if account.balance - cents < -account.limit:
        raise InsufficientFunds(account_id)
    account.balance -= cents
    book.post(day, account_id, -cents, memo)
    return cents


def _credit(book, account_id, cents, day, memo):
    account = book.get(account_id)
    if account.frozen:
        raise FrozenAccount(account_id)
    account.balance += cents
    book.post(day, account_id, cents, memo)


def transfer(book, source, target, amount, day=None, memo="transfer"):
    """Move `amount` from `source` to `target`, both in one currency. Returns the cents moved."""
    if source == target:
        raise LedgerError("a transfer needs two accounts")
    if book.get(source).currency != book.get(target).currency:
        raise LedgerError("a transfer between currencies is not supported")
    if book.get(target).frozen:
        raise FrozenAccount(target)
    day = day or _today()
    cents = _debit(book, source, amount, day, memo)
    _credit(book, target, cents, day, memo)
    return cents


def withdraw(book, account_id, amount, day=None, memo="withdrawal"):
    """Pay `amount` out of the account. Returns the cents taken."""
    return _debit(book, account_id, amount, day or _today(), memo)
PY

cat > ledger/fees.py <<'PY'
"""The monthly account fee (LD-5), charged through the shared debit."""

from ledger.errors import InsufficientFunds
from ledger.ops import _debit

MONTHLY_FEE = "4.35"


def charge_monthly_fees(book, day):
    """Charge the monthly fee to every account that is not frozen. Returns the ids charged and
    the ids whose overdraft limit left no room for it."""
    charged, short = [], []
    for account in sorted(book.accounts.values(), key=lambda account: account.id):
        if account.frozen:
            continue
        try:
            _debit(book, account.id, MONTHLY_FEE, day, "monthly fee")
        except InsufficientFunds:
            short.append(account.id)
        else:
            charged.append(account.id)
    return charged, short
PY

cat > ledger/statement.py <<'PY'
"""An account's statement: its postings, oldest first (LD-4), with the running balance."""

from ledger.display import format_amount


def statement(book, account_id):
    account = book.get(account_id)
    entries = [entry for entry in book.journal if entry["account"] == account_id]
    running = account.balance - sum(entry["cents"] for entry in entries)
    body = []
    for entry in entries:
        running += entry["cents"]
        body.append(
            f"{entry['day']}  {format_amount(entry['cents']):>10}  "
            f"{format_amount(running):>10}  {entry['memo']}"
        )
    head = f"{account.id}  {account.owner}  ({account.currency})"
    return [head, *body, f"balance {format_amount(account.balance)}"]
PY

cat > ledger/cli.py <<'PY'
"""The command line: python3 -m ledger [--data DIR] balance|statement|transfer|withdraw ..."""

import argparse
import sys

from ledger import ops
from ledger.accounts import load_book, save_book
from ledger.display import format_amount
from ledger.errors import LedgerError
from ledger.statement import statement


def parser():
    found = argparse.ArgumentParser(prog="ledger")
    found.add_argument("--data", default="data", help="the book's folder (default: data)")
    commands = found.add_subparsers(dest="command", required=True)
    balance = commands.add_parser("balance", help="print an account's balance")
    balance.add_argument("account")
    show = commands.add_parser("statement", help="print an account's statement")
    show.add_argument("account")
    move = commands.add_parser("transfer", help="move money between two accounts")
    move.add_argument("source")
    move.add_argument("target")
    move.add_argument("amount")
    out = commands.add_parser("withdraw", help="pay money out of an account")
    out.add_argument("account")
    out.add_argument("amount")
    return found


def main(argv=None):
    args = parser().parse_args(argv)
    book = load_book(args.data)
    try:
        if args.command == "balance":
            print(format_amount(book.get(args.account).balance))
            return 0
        if args.command == "statement":
            print("\n".join(statement(book, args.account)))
            return 0
        if args.command == "transfer":
            ops.transfer(book, args.source, args.target, args.amount)
        else:
            ops.withdraw(book, args.account, args.amount)
    except LedgerError as problem:
        print(f"ledger: {problem}", file=sys.stderr)
        return 1
    save_book(book, args.data)
    return 0
PY

cat > data/accounts.json <<'JSON'
[
  {
    "id": "acc-001",
    "owner": "Harbour Bakery",
    "currency": "EUR",
    "balance": 125000,
    "limit": 0,
    "frozen": false
  },
  {
    "id": "acc-002",
    "owner": "North Mill Co-op",
    "currency": "EUR",
    "balance": 4210,
    "limit": 5000,
    "frozen": false
  },
  {
    "id": "acc-003",
    "owner": "Lantern Books",
    "currency": "EUR",
    "balance": -1250,
    "limit": 5000,
    "frozen": false
  },
  {
    "id": "acc-004",
    "owner": "Quay Street Garage",
    "currency": "EUR",
    "balance": 30000,
    "limit": 0,
    "frozen": true
  }
]
JSON

cat > data/journal.jsonl <<'JSONL'
{"account": "acc-001", "cents": 125000, "day": "2026-09-01", "memo": "opening"}
{"account": "acc-002", "cents": 9210, "day": "2026-09-01", "memo": "opening"}
{"account": "acc-003", "cents": 3500, "day": "2026-09-01", "memo": "opening"}
{"account": "acc-004", "cents": 30000, "day": "2026-09-01", "memo": "opening"}
{"account": "acc-002", "cents": -5000, "day": "2026-09-14", "memo": "withdrawal"}
{"account": "acc-003", "cents": -4750, "day": "2026-09-22", "memo": "withdrawal"}
JSONL

cat > tests/__init__.py <<'PY'
PY
cat > tests/unit/__init__.py <<'PY'
PY
cat > tests/integration/__init__.py <<'PY'
PY

cat > tests/unit/helpers.py <<'PY'
from ledger.accounts import Account, Book


def book(*accounts):
    """A book holding `accounts`, each (id, balance in cents) or an Account."""
    found = Book()
    for account in accounts:
        if not isinstance(account, Account):
            account_id, balance = account
            account = Account(account_id, "test", balance=balance)
        found.add(account)
    return found
PY

cat > tests/unit/test_money.py <<'PY'
import unittest

from ledger.errors import LedgerError
from ledger.money import to_cents


class ToCentsTest(unittest.TestCase):
    def test_text_with_two_places(self):
        self.assertEqual(to_cents("12.30"), 1230)

    def test_whole_units(self):
        self.assertEqual(to_cents("5"), 500)

    def test_one_place(self):
        self.assertEqual(to_cents("0.5"), 50)

    def test_more_than_two_places_is_refused(self):
        with self.assertRaises(LedgerError):
            to_cents("1.234")

    def test_text_that_is_no_amount_is_refused(self):
        with self.assertRaises(LedgerError):
            to_cents("twelve")
PY

cat > tests/unit/test_display.py <<'PY'
import unittest

from ledger.display import format_amount


class FormatAmountTest(unittest.TestCase):
    def test_units_and_cents(self):
        self.assertEqual(format_amount(1234), "12.34")

    def test_cents_only(self):
        self.assertEqual(format_amount(5), "0.05")

    def test_zero(self):
        self.assertEqual(format_amount(0), "0.00")
PY

cat > tests/unit/test_ops.py <<'PY'
import unittest

from ledger import ops
from ledger.accounts import Account
from ledger.errors import FrozenAccount, InsufficientFunds, LedgerError
from tests.unit.helpers import book

DAY = "2026-10-01"


class TransferTest(unittest.TestCase):
    def test_moves_the_amount(self):
        found = book(("a", 5000), ("b", 0))
        self.assertEqual(ops.transfer(found, "a", "b", "10.00", day=DAY), 1000)
        self.assertEqual((found.get("a").balance, found.get("b").balance), (4000, 1000))

    def test_journal_records_both_sides(self):
        found = book(("a", 5000), ("b", 0))
        ops.transfer(found, "a", "b", "10.00", day=DAY)
        self.assertEqual([entry["cents"] for entry in found.journal], [-1000, 1000])

    def test_too_little_money(self):
        found = book(("a", 500), ("b", 0))
        with self.assertRaises(InsufficientFunds):
            ops.transfer(found, "a", "b", "10.00", day=DAY)
        self.assertEqual(found.get("a").balance, 500)

    def test_frozen_target_moves_nothing(self):
        found = book(("a", 5000), Account("b", "test", frozen=True))
        with self.assertRaises(FrozenAccount):
            ops.transfer(found, "a", "b", "10.00", day=DAY)
        self.assertEqual(found.get("a").balance, 5000)

    def test_between_currencies_is_refused(self):
        found = book(("a", 5000), Account("b", "test", currency="CHF"))
        with self.assertRaises(LedgerError):
            ops.transfer(found, "a", "b", "10.00", day=DAY)


class WithdrawTest(unittest.TestCase):
    def test_takes_the_amount(self):
        found = book(("a", 5000))
        ops.withdraw(found, "a", "20.00", day=DAY)
        self.assertEqual(found.get("a").balance, 3000)

    def test_within_the_overdraft_limit(self):
        found = book(Account("a", "test", balance=1000, limit=2000))
        ops.withdraw(found, "a", "25.00", day=DAY)
        self.assertEqual(found.get("a").balance, -1500)

    def test_zero_is_refused(self):
        found = book(("a", 5000))
        with self.assertRaises(LedgerError):
            ops.withdraw(found, "a", "0", day=DAY)
PY

cat > tests/unit/test_fees.py <<'PY'
import unittest

from ledger.accounts import Account
from ledger.fees import charge_monthly_fees
from tests.unit.helpers import book


class MonthlyFeeTest(unittest.TestCase):
    def test_every_open_account_is_charged(self):
        found = book(("a", 10000), ("b", 2000))
        charged, short = charge_monthly_fees(found, "2026-10-01")
        self.assertEqual((charged, short), (["a", "b"], []))
        self.assertEqual(found.get("a").balance, 10000 - 435)

    def test_frozen_accounts_are_not_charged(self):
        found = book(("a", 10000), Account("f", "test", balance=10000, frozen=True))
        charged, _ = charge_monthly_fees(found, "2026-10-01")
        self.assertEqual(charged, ["a"])
        self.assertEqual(found.get("f").balance, 10000)

    def test_no_room_in_the_limit(self):
        found = book(("a", 100))
        self.assertEqual(charge_monthly_fees(found, "2026-10-01"), ([], ["a"]))
PY

cat > tests/unit/test_statement.py <<'PY'
import unittest

from ledger import ops
from ledger.statement import statement
from tests.unit.helpers import book


class StatementTest(unittest.TestCase):
    def test_oldest_first_with_the_running_balance(self):
        found = book(("a", 5000), ("b", 0))
        ops.withdraw(found, "a", "10.00", day="2026-10-01")
        ops.withdraw(found, "a", "5.00", day="2026-10-02")
        lines = statement(found, "a")
        self.assertIn("2026-10-01", lines[1])
        self.assertIn("40.00", lines[1])
        self.assertIn("2026-10-02", lines[2])
        self.assertEqual(lines[-1], "balance 35.00")
PY

cat > tests/integration/test_flows.py <<'PY'
"""The integration suite: the posting flows end to end, over a book on disk. It takes about a
minute, as each flow waits for its batch to settle the way the posting service does. Each run
is logged in .runs/integration.log: a `start` line when it begins and a `suite` line when it ends.

It covers ledger/ops.py, ledger/fees.py and the book on disk (ledger/accounts.py); it does not
reach the command line, statements or how amounts are displayed."""

import datetime
import json
import tempfile
import time
import unittest
from pathlib import Path

from ledger import ops
from ledger.accounts import Account, Book, load_book, save_book
from ledger.errors import FrozenAccount
from ledger.fees import charge_monthly_fees

LOG = Path(__file__).resolve().parents[2] / ".runs" / "integration.log"
SETTLE = 15  # seconds a batch takes to settle


def _log(kind, **extra):
    LOG.parent.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": kind, "at": stamp, **extra}) + "\n")


def setUpModule():
    _log("start")


def tearDownModule():
    _log("suite")


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="ledger-flow-"))
        book = Book()
        book.add(Account("a", "flow", balance=50000))
        book.add(Account("b", "flow", balance=1000, limit=2000))
        book.add(Account("f", "flow", balance=7000, frozen=True))
        save_book(book, self.folder)

    def settle(self):
        time.sleep(SETTLE)
        return load_book(self.folder)

    def test_transfer_round_trip(self):
        book = load_book(self.folder)
        ops.transfer(book, "a", "b", "125.50", day="2026-10-01")
        ops.transfer(book, "b", "a", "25.50", day="2026-10-02")
        save_book(book, self.folder)
        book = self.settle()
        self.assertEqual((book.get("a").balance, book.get("b").balance), (40000, 11000))

    def test_withdraw_into_the_overdraft(self):
        book = load_book(self.folder)
        ops.withdraw(book, "b", "25.00", day="2026-10-01")
        save_book(book, self.folder)
        self.assertEqual(self.settle().get("b").balance, -1500)

    def test_a_month_of_fees(self):
        book = load_book(self.folder)
        charged, short = charge_monthly_fees(book, "2026-10-01")
        save_book(book, self.folder)
        book = self.settle()
        self.assertEqual((charged, short), (["a", "b"], []))
        self.assertEqual(book.get("f").balance, 7000)

    def test_frozen_account_refuses(self):
        book = load_book(self.folder)
        with self.assertRaises(FrozenAccount):
            ops.withdraw(book, "f", "1.00", day="2026-10-01")
        self.settle()
PY

cat > Makefile <<'MAKE'
PYTHON ?= python3

.PHONY: unit integration test

# The unit tests, under two seconds.
unit:
	$(PYTHON) -B -m unittest discover -s tests/unit -t .

# The integration suite: the posting flows end to end, about a minute.
integration:
	$(PYTHON) -B -m unittest discover -s tests/integration -t .

# The full suite: unit and integration.
test: unit integration
MAKE

cat > .gitignore <<'TXT'
__pycache__/
.runs/
TXT

cat > README.md <<'MD'
# ledger

A small money service: accounts, transfers, withdrawals and the monthly fee, kept as JSON under
`data/`, with a command line.

    python3 -m ledger balance acc-001
    python3 -m ledger statement acc-002
    python3 -m ledger transfer acc-001 acc-002 12.50
    python3 -m ledger withdraw acc-002 5.00

`make unit` runs the unit tests, `make integration` the integration suite, `make test` both.
MD

cat > CHANGELOG.md <<'MD'
# Changelog

## Unreleased

## 0.9.0 (2026-07-01)

- The monthly fee (LD-5).
- Statements list the oldest posting first again (LD-4).
- The integration suite of the posting flows.

## 0.8.0 (2026-04-06)

- The command line: balance, statement, transfer and withdraw.
MD

cat > CONTRIBUTING.md <<'MD'
# Contributing

Thank you for helping. Every change, however small, comes with:

1. a design note under `docs/notes/` saying what changed and why;
2. an entry under "Unreleased" in `CHANGELOG.md`;
3. the full suite, `make test` (unit and integration), green before you call it done.

## Migrations

`data/` is the live book. A migration that rewrites it is run by the book's owner, after a backup
they take. Write a migration and test it on a copy; never run one on `data/`.

## Locks

A tool that writes under `data/` holds a lock file beside what it writes while it works. Remove a
lock by hand only once the process that holds it no longer runs.
MD

cat > docs/decisions.md <<'MD'
# Decisions

Each decision has an id (LD-n), a date and what it settles. A later decision may revert an earlier
one; the earlier entry stays, marked as reverted.

## LD-1 (2026-03-02): amounts are whole cents inside the ledger

Amounts arrive as text ("12.30") and are held as whole cents. No float touches an amount:
`ledger.money.to_cents` is the one way in.

## LD-2 (2026-04-06): statements list the newest posting first (reverted by LD-4)

## LD-3 (2026-04-06): amounts leave the ledger as text with two decimal places

Whatever prints or writes an amount, for a person or for another system, uses
`ledger.display.format_amount`: "-12.50", never cents.

## LD-4 (2026-06-08): statements list the oldest posting first (reverts LD-2)

The reconciliation team reads a statement from the top and matched the newest-first order
against the wrong opening balance twice. Oldest first, as the journal holds them.

## LD-5 (2026-04-27): the monthly fee is 4.35

Charged on the first of the month to every account that is not frozen. An account whose overdraft
limit leaves no room for it is listed, not charged.
MD

cat > docs/tickets/README.md <<'MD'
# Tickets

One file a ticket, `NNN-name.md`: what becomes true (Outcome), its Status, and what is still open.
MD

cat > docs/tickets/005-integration-suite.md <<'MD'
# 005 An integration suite for the posting flows

Outcome: transfers, withdrawals and the monthly fee run end to end over a book on disk, as the
posting service runs them, in `make integration`.

Status: done (0.9.0).
MD
