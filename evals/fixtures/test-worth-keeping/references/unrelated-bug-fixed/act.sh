#!/usr/bin/env bash
# unrelated-bug-fixed: a good test, and the calendar bug fixed beside it so that the earlier failing test passes.
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
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('dates.py')
text = path.read_text(encoding="utf-8")
old = 'return month // 3 + 1'
new = 'return (month - 1) // 3 + 1'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
