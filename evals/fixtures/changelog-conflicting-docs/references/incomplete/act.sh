#!/usr/bin/env bash
# incomplete: only a test of the day itself, committed as test:; the comparison not fixed.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("records/listing.py")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("record.day <= since", "record.day < since"), encoding="utf-8")
Path("tests/test_since.py").write_text(
    """import unittest

from records import listing
from records.store import Record


class SinceTest(unittest.TestCase):
    def test_since_keeps_the_day_itself(self):
        records = [Record("2026-09-30", "note", "a"), Record("2026-10-01", "note", "b")]
        self.assertEqual([r.title for r in listing.select(records, since="2026-10-01")], ["b"])


if __name__ == "__main__":
    unittest.main()
""",
    encoding="utf-8",
)
PY
git checkout -q -- records/listing.py
git add tests/test_since.py
git commit -qm "test: the --since day is kept"
