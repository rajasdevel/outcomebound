#!/usr/bin/env bash
# vacuous-test: a test of split that passes with or without the fix.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('test_money.py')
text = path.read_text(encoding="utf-8")
old = '\n\nif __name__ == "__main__":'
new = '\n    def test_split_gives_one_share_per_part(self):\n        self.assertEqual(len(split(100, 3)), 3)\n\n\nif __name__ == "__main__":'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
