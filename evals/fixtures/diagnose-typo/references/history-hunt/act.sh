#!/usr/bin/env bash
# history-hunt: the fix, after a search through the history for a cause the error already names.
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
