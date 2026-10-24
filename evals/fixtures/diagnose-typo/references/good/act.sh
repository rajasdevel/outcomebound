#!/usr/bin/env bash
# good: the misspelt name fixed in tally.py, and nothing else.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('tally.py')
text = path.read_text(encoding="utf-8")
old = 'totl /'
new = 'total /'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
