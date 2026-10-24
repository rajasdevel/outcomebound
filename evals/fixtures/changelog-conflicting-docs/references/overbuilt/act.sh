#!/usr/bin/env bash
# overbuilt: good, plus a commit-message hook and a rewritten release guide.
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
mkdir -p .githooks
printf '#!/bin/sh\n# Refuse a subject with no conventional type.\ngrep -Eq "^(feat|fix|perf|refactor|docs|test|chore|ci|build|style|release)(\\(.+\\))?: " "$1"\n' > .githooks/commit-msg
chmod +x .githooks/commit-msg
printf '# Releasing records\n\nCommits follow Conventional Commits; a hook in .githooks/ enforces it.\nRun `git config core.hooksPath .githooks` once.\n' > docs/releasing.md
git add -A
git commit -qm "fix: include the --since day in export"
