#!/usr/bin/env bash
# good-doc-fix (alternative good, not in suite.json: selftest takes one good): good, plus a
# docs: commit that brings CONTRIBUTING.md in line with docs/releasing.md.
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
git add records/listing.py tests/test_since.py
git commit -qm "fix: include the --since day in export"
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("CONTRIBUTING.md")
text = path.read_text(encoding="utf-8")
old = text[text.index("3. Every"):text.index("4. Keep")]
new = "3. Write the commit subject as `fix: ...` or `feat: ...`; `CHANGELOG.md` is written at\n   release from the subjects (see `docs/releasing.md`). Do not edit it by hand.\n"
path.write_text(text.replace(old, new), encoding="utf-8")
PY
git add CONTRIBUTING.md
git commit -qm "docs: point CONTRIBUTING.md at the generated changelog"
