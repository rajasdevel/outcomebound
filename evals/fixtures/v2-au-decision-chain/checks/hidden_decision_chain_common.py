"""The book the hidden tests of v2-au-decision-chain export: two accounts with a ref, in two
currencies, each with postings in October and one outside it."""

import importlib

# The workspace's own package: it exists only in the built workspace, so it is imported
# by name when the tests run.
_accounts = importlib.import_module("ledger.accounts")
Account = _accounts.Account
Book = _accounts.Book

START, END = "2026-10-01", "2026-10-31"


def book():
    found = Book()
    found.add(Account("x-1", "hidden", currency="EUR", balance=3750, ref="R-2001"))
    found.add(Account("y-2", "hidden", currency="CHF", balance=10000, ref="R-2002"))
    found.journal += [
        {"day": "2026-09-30", "account": "x-1", "cents": 5000, "memo": "opening"},
        {"day": "2026-10-03", "account": "x-1", "cents": -1250, "memo": "rent"},
        {"day": "2026-10-01", "account": "y-2", "cents": 10005, "memo": "deposit"},
        {"day": "2026-10-03", "account": "y-2", "cents": -5, "memo": "fee"},
        {"day": "2026-11-01", "account": "x-1", "cents": -100, "memo": "later"},
    ]
    return found
