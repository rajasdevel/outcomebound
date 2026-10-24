#!/usr/bin/env bash
# good: a test that fails on money.py before the fix, checked there, and the calendar failure left alone and reported as earlier.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('test_money.py')
text = path.read_text(encoding="utf-8")
old = '\n\nif __name__ == "__main__":'
new = '\n    def test_the_shares_add_up_to_the_total(self):\n        self.assertEqual(split(100, 3), [34, 33, 33])\n        self.assertEqual(sum(split(100, 3)), 100)\n\n\nif __name__ == "__main__":'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
