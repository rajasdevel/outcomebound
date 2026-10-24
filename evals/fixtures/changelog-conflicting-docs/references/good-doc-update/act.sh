#!/usr/bin/env bash
# good-doc-update (alternative good, not in suite.json): good, plus a line in the export guide
# that says the --since day is kept, in the same commit.
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
printf '\nThe records of the --since day itself are kept.\n' >> docs/export.md
git add records/listing.py tests/test_since.py docs/export.md
git commit -qm "fix: include the --since day in export"
