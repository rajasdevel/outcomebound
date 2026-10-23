import unittest

from records import listing
from records.store import Record


class UntilTest(unittest.TestCase):
    def test_until_keeps_the_day_itself(self):
        records = [Record("2026-10-01", "note", "a"), Record("2026-10-02", "note", "b")]
        self.assertEqual([r.title for r in listing.select(records, until="2026-10-01")], ["a"])


if __name__ == "__main__":
    unittest.main()
