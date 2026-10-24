import io
import unittest

from records import listing
from records.store import Record

RECORDS = [
    Record("2026-09-20", "note", "a"),
    Record("2026-09-25", "call", "b"),
    Record("2026-10-03", "note", "c"),
]


class SelectTest(unittest.TestCase):
    def test_no_filter_keeps_everything_in_order(self):
        self.assertEqual(listing.select(RECORDS), RECORDS)

    def test_since_drops_earlier_days(self):
        self.assertEqual([r.title for r in listing.select(RECORDS, since="2026-09-22")], ["b", "c"])

    def test_kind(self):
        self.assertEqual([r.title for r in listing.select(RECORDS, kind="note")], ["a", "c"])


class WriteTest(unittest.TestCase):
    def test_header_and_rows(self):
        out = io.StringIO()
        listing.write(RECORDS[:1], out)
        self.assertEqual(out.getvalue(), "day,kind,title\n2026-09-20,note,a\n")


if __name__ == "__main__":
    unittest.main()
