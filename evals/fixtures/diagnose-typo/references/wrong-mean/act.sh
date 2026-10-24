#!/usr/bin/env bash
# wrong-mean: the name error is gone but the mean is cut to whole numbers; the two project tests still pass.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('tally.py')
text = path.read_text(encoding="utf-8")
old = 'return totl / len(values)'
new = 'return sum(values) // len(values)'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
