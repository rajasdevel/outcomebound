#!/usr/bin/env bash
# contributing-follower: CONTRIBUTING.md followed: a line under Unreleased and a free-form subject.
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
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("CHANGELOG.md")
text = path.read_text(encoding="utf-8")
path.write_text(
    text.replace("## Unreleased\n", "## Unreleased\n\n- Fixed `export --since` leaving out the day itself.\n", 1),
    encoding="utf-8",
)
PY
git add -A
git commit -qm "Fix since filter"
