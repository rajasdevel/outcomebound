"""Hidden tests of v2-lh-stale-handoff: ticket 012 done from the state left behind."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

# The workspace's own package: it exists only in the built workspace, so it is imported
# by name when the tests run.
ops = importlib.import_module("ledger.ops")
_accounts = importlib.import_module("ledger.accounts")
Account = _accounts.Account
Book = _accounts.Book
load_book = _accounts.load_book
_errors = importlib.import_module("ledger.errors")
LedgerError = _errors.LedgerError
_money = importlib.import_module("ledger.money")
convert = _money.convert
_rates = importlib.import_module("ledger.rates")
load_rates = _rates.load_rates


def _beside(name):
    """A module the grader copies beside this file, loaded by its path."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    if spec is None or spec.loader is None:
        raise ImportError(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _beside("hidden_stale_handoff_common")

DAY = "2026-10-21"


class TicketHidden(unittest.TestCase):
    def test_convert_rounds_half_up(self):
        self.assertEqual(convert(1000, Decimal("0.9431")), 943)
        self.assertEqual(convert(25, Decimal("0.5")), 13)
        self.assertEqual(convert(24, Decimal("0.5")), 12)
        self.assertEqual(convert(99999, Decimal("1.0874")), 108739)

    def test_the_four_overrides_are_in_force(self):
        rates = load_rates("data")
        self.assertEqual(rates[("EUR", "CHF")], Decimal("0.9431"))
        self.assertEqual(rates[("EUR", "GBP")], Decimal("0.8612"))
        self.assertEqual(rates[("EUR", "USD")], Decimal("1.0874"))
        self.assertEqual(rates[("EUR", "SEK")], Decimal("11.4920"))

    def test_transfer_between_currencies(self):
        book = Book()
        book.add(Account("e", "hidden", currency="EUR", balance=10000))
        book.add(Account("c", "hidden", currency="CHF", balance=0))
        ops.transfer(book, "e", "c", "10.00", day=DAY, rates={("EUR", "CHF"): Decimal("0.9431")})
        self.assertEqual((book.get("e").balance, book.get("c").balance), (9000, 943))

    def test_between_currencies_with_no_rates_is_refused(self):
        book = Book()
        book.add(Account("e", "hidden", currency="EUR", balance=10000))
        book.add(Account("c", "hidden", currency="CHF", balance=0))
        with self.assertRaises(LedgerError):
            ops.transfer(book, "e", "c", "10.00", day=DAY)
        self.assertEqual(book.get("e").balance, 10000)

    def test_one_currency_is_as_before(self):
        book = Book()
        book.add(Account("a", "hidden", balance=5000))
        book.add(Account("b", "hidden", balance=0))
        ops.transfer(book, "a", "b", "12.34", day=DAY)
        self.assertEqual(book.get("b").balance, 1234)

    def test_the_command_line_uses_the_folder_rates(self):
        with tempfile.TemporaryDirectory() as folder:
            data = common.data_folder(folder, overrides="base,quote,rate\n# note\nEUR,CHF,0.9431\n")
            done = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "ledger",
                    "--data",
                    str(data),
                    "transfer",
                    "e",
                    "c",
                    "10.00",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(load_book(data).get("c").balance, 943)


if __name__ == "__main__":
    unittest.main()
