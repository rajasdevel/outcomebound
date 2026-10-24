#!/usr/bin/env bash
# wrong-expectation: a test that expects the extra cent on the last share, so it fails with the fix in place.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('test_money.py')
text = path.read_text(encoding="utf-8")
old = '\n\nif __name__ == "__main__":'
new = '\n    def test_the_shares_add_up_to_the_total(self):\n        self.assertEqual(split(100, 3), [33, 33, 34])\n\n\nif __name__ == "__main__":'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
