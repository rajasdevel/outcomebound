#!/usr/bin/env bash
# unreproduced: the loader is fixed from reading the code; the function was only searched for, never called, and the answer says so.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('bizdays.py')
text = path.read_text(encoding="utf-8")
old = '            days.add(line)\n'
new = '            days.add(line.split()[0])\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
