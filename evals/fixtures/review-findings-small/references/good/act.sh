#!/usr/bin/env bash
# good: the docstring says the bounds are included, the code unchanged, a bound test added, R1 recorded as fixed.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('clamp.py')
text = path.read_text(encoding="utf-8")
old = 'both excluded'
new = 'both included'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('test_clamp.py')
text = path.read_text(encoding="utf-8")
old = '\n\nif __name__'
new = '\n    def test_a_value_on_a_bound_is_unchanged(self):\n        self.assertEqual(clamp(0, 0, 10), 0)\n        self.assertEqual(clamp(10, 0, 10), 10)\n\n\nif __name__'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('reviews/clamp.md')
text = path.read_text(encoding="utf-8")
old = 'The docstring\nshould say so.\n'
new = 'The docstring\nshould say so.\n\nDisposition: fixed — the docstring of clamp.py now says the bounds are included\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
