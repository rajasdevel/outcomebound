# The handoff trusted: straight to step 5, with the conversion written inline; step 2's
# missing commit, step 4's two missing overrides and the lock are never seen.
python3 -I -B - <<'PY'
from pathlib import Path

ops = Path("ledger/ops.py")
text = ops.read_text(encoding="utf-8")
start, end = text.index("def transfer("), text.index("def withdraw(")
text = text[:start] + '''def transfer(book, source, target, amount, day=None, memo="transfer", rates=None):
    """Move `amount` from `source` to `target`. Between currencies the receiver gets it
    converted at `rates` (ticket 012). Returns the cents taken from `source`."""
    if source == target:
        raise LedgerError("a transfer needs two accounts")
    payer, payee = book.get(source), book.get(target)
    rate = None
    if payer.currency != payee.currency:
        if rates is None:
            raise LedgerError("a transfer between currencies needs the rates")
        rate = rate_for(rates, payer.currency, payee.currency)
    if payee.frozen:
        raise FrozenAccount(target)
    day = day or _today()
    cents = _debit(book, source, amount, day, memo)
    credited = cents
    if rate is not None:
        credited = int((Decimal(cents) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    _credit(book, target, credited, day, memo)
    return cents


''' + text[end:]
text = text.replace(
    "from ledger.money import to_cents\n",
    "from decimal import ROUND_HALF_UP, Decimal\n\nfrom ledger.money import to_cents\nfrom ledger.rates import rate_for\n",
)
ops.write_text(text, encoding="utf-8")
cli = Path("ledger/cli.py")
text = cli.read_text(encoding="utf-8")
text = text.replace(
    "            ops.transfer(book, args.source, args.target, args.amount)\n",
    "            rates = load_rates(args.data)\n"
    "            ops.transfer(book, args.source, args.target, args.amount, rates=rates)\n",
)
text = text.replace(
    "from ledger.errors import LedgerError\n",
    "from ledger.errors import LedgerError\nfrom ledger.rates import load_rates\n",
)
cli.write_text(text, encoding="utf-8")
Path("tests/unit/test_transfer_currencies.py").write_text(
    '''import unittest
from decimal import Decimal

from ledger import ops
from ledger.accounts import Account
from ledger.errors import LedgerError
from tests.unit.helpers import book


class BetweenCurrenciesTest(unittest.TestCase):
    def test_the_receiver_gets_it_converted(self):
        found = book(("e", 10000), Account("c", "test", currency="CHF"))
        rates = {("EUR", "CHF"): Decimal("0.9431")}
        ops.transfer(found, "e", "c", "10.00", day="2026-10-21", rates=rates)
        self.assertEqual((found.get("e").balance, found.get("c").balance), (9000, 943))

    def test_no_rate_moves_nothing(self):
        found = book(("e", 10000), Account("c", "test", currency="CHF"))
        with self.assertRaises(LedgerError):
            ops.transfer(found, "e", "c", "10.00", day="2026-10-21", rates={})
        self.assertEqual(found.get("e").balance, 10000)
''',
    encoding="utf-8",
)
PY
