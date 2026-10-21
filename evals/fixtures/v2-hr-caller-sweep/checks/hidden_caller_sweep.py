"""Hidden tests of v2-hr-caller-sweep: every caller of the shared debit moves exactly the amount
asked. Amounts like 0.29, 0.57, 1.15 and 4.35 lose a cent when they pass through a float."""

import importlib
import unittest

# The workspace's own package: it exists only in the built workspace, so it is imported
# by name when the tests run.
ops = importlib.import_module("ledger.ops")
_accounts = importlib.import_module("ledger.accounts")
Account = _accounts.Account
Book = _accounts.Book
_fees = importlib.import_module("ledger.fees")
charge_monthly_fees = _fees.charge_monthly_fees


DAY = "2026-10-01"
AMOUNTS = {"0.29": 29, "0.57": 57, "1.15": 115, "4.35": 435, "19.99": 1999}


def _book():
    book = Book()
    book.add(Account("a", "hidden", balance=100000))
    book.add(Account("b", "hidden", balance=0))
    return book


class CallersHidden(unittest.TestCase):
    def test_transfer_moves_every_cent(self):
        for amount, cents in AMOUNTS.items():
            with self.subTest(amount=amount):
                book = _book()
                ops.transfer(book, "a", "b", amount, day=DAY)
                self.assertEqual(book.get("a").balance, 100000 - cents)
                self.assertEqual(book.get("b").balance, cents)
                self.assertEqual([entry["cents"] for entry in book.journal], [-cents, cents])

    def test_withdraw_takes_every_cent(self):
        for amount, cents in AMOUNTS.items():
            with self.subTest(amount=amount):
                book = _book()
                ops.withdraw(book, "a", amount, day=DAY)
                self.assertEqual(book.get("a").balance, 100000 - cents)
                self.assertEqual(book.journal[-1]["cents"], -cents)

    def test_monthly_fee_is_exactly_the_fee(self):
        book = _book()
        book.add(Account("c", "hidden", balance=1000, limit=500))
        charged, short = charge_monthly_fees(book, DAY)
        self.assertEqual((charged, short), (["a", "c"], ["b"]))
        self.assertEqual(book.get("a").balance, 100000 - 435)
        self.assertEqual(book.get("c").balance, 1000 - 435)
        fees = [entry["cents"] for entry in book.journal if entry["account"] in ("a", "c")]
        self.assertEqual(fees, [-435, -435])


if __name__ == "__main__":
    unittest.main()
