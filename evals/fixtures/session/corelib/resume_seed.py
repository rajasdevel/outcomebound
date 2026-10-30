"""Seed existing defects and preserved operator work, without a future work list."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

write = runpy.run_path(str(Path(__file__).with_name("build.py")))["write"]

for name, before, after in (
    ("tally/selection.py", "entry.day > self.until", "entry.day >= self.until"),
    ("tally/reconcile.py", "entry.minutes, entry.note", "entry.minutes"),
    ("tests/test_selection.py", "test_inclusive", "test_lower_bound"),
    ("tests/test_selection.py", 'Selection("2026-04-02", "2026-04-03")', 'Selection("2026-04-02")'),
):
    path = Path(name)
    path.write_text(path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")
Path("tickets/history").mkdir(parents=True, exist_ok=True)
for path in Path("tickets").glob("*.md"):
    path.rename(path.parent / "history" / path.name)
write(
    "tests/known_baseline.py",
    '''
    """Known defect: prerelease headings are not accepted by the release reader."""
    import unittest
    from tally.release import released_section

    class KnownBaselineTest(unittest.TestCase):
        def test_prerelease(self):
            self.assertEqual(released_section('## 3.3.0-rc1\\n\\n- Candidate.\\n', '3.3.0-rc1'),
                             '- Candidate.')
    ''',
)
write("cache/old-index.json", '{"obsolete": true}\n')
write("docs/operator-notes.md", "# Operator notes\n\nCurrent export checks.\n")
write(
    "records/progress.json",
    json.dumps(
        {
            "tickets": {},
            "checks": [],
            "next": "021",
            "recovery": {"comparison_key": "closed-window-note-lines"},
        }
    )
    + "\n",
)
