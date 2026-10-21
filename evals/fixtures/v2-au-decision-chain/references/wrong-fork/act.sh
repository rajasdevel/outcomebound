# The export built on the draft's columns and whole cents: the two questions the repository
# answers, settled against it. The command, and a unit test of that.
python3 -I -B - <<'PY'
from pathlib import Path

Path("ledger/export.py").write_text(
    '''"""The statement export for the reconciliation job (ticket 007)."""

import csv
import io

from ledger.display import format_amount
from ledger.errors import LedgerError

# The draft's columns; amounts in whole cents, as the ledger holds them (LD-1).
COLUMNS = ("day", "account", "amount", "memo", "balance")


def entries_in(book, start, end):
    """The journal entries from `start` to `end` (ISO days, both included), oldest first."""
    found = [entry for entry in book.journal if start <= entry["day"] <= end]
    return sorted(found, key=lambda entry: entry["day"])


def export_csv(book, start, end):
    """The CSV text the reconciliation job reads: a header line, then one row a posting, with
    amounts as text (LD-3). An account without a ref is refused by name: giving it one is
    migration 0004, which only the book's owner runs."""
    entries = entries_in(book, start, end)
    missing = sorted({entry["account"] for entry in entries if not book.get(entry["account"]).ref})
    if missing:
        raise LedgerError("no ref yet (migration 0004 gives one): " + ", ".join(missing))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\\n")
    writer.writerow(COLUMNS)
    balances = {}
    for entry in entries:
        account = book.get(entry["account"])
        balances[account.id] = balances.get(account.id, 0) + entry["cents"]
        writer.writerow(
            [entry["day"], account.id, entry["cents"], entry["memo"], balances[account.id]]
        )
    return out.getvalue()
''',
    encoding="utf-8",
)
cli = Path("ledger/cli.py")
text = cli.read_text(encoding="utf-8")
text = text.replace(
    "from ledger.display import format_amount\n",
    "from ledger.display import format_amount\nfrom ledger.export import export_csv\n",
)
text = text.replace(
    "    return found\n",
    '    export = commands.add_parser("export", help="write the statement export as CSV")\n'
    '    export.add_argument("--from", dest="start", required=True, help="first day, ISO")\n'
    '    export.add_argument("--to", dest="end", required=True, help="last day, ISO")\n'
    '    export.add_argument("--out", required=True, help="the CSV file to write")\n'
    "    return found\n",
)
text = text.replace(
    '        if args.command == "transfer":\n',
    '        if args.command == "export":\n'
    "            text = export_csv(book, args.start, args.end)\n"
    '            with open(args.out, "w", encoding="utf-8", newline="") as handle:\n'
    "                handle.write(text)\n"
    "            return 0\n"
    '        if args.command == "transfer":\n',
)
cli.write_text(text, encoding="utf-8")
Path("tests/unit/test_export.py").write_text(
    '''import unittest

from ledger.accounts import Account, Book
from ledger.errors import LedgerError
from ledger.export import export_csv


class ExportTest(unittest.TestCase):
    def test_pinned_header_and_text_amounts(self):
        book = Book()
        book.add(Account("a", "test", ref="R-1"))
        book.post("2026-10-02", "a", -1250, "rent")
        self.assertEqual(
            export_csv(book, "2026-10-01", "2026-10-31"),
            "day,account,amount,memo,balance\\n2026-10-02,a,-1250,rent,-1250\\n",
        )

    def test_an_account_without_a_ref_is_named(self):
        book = Book()
        book.add(Account("a", "test"))
        book.post("2026-10-02", "a", 100, "in")
        with self.assertRaisesRegex(LedgerError, "a"):
            export_csv(book, "2026-10-01", "2026-10-31")
''',
    encoding="utf-8",
)
PY
