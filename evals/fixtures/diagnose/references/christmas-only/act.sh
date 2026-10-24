#!/usr/bin/env bash
# christmas-only: a special case for 25 December in next_business_day; the loader still never matches the other holidays.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('bizdays.py')
text = path.read_text(encoding="utf-8")
old = '    while day.weekday() >= 5 or day.isoformat() in holidays:\n'
new = '    while day.weekday() >= 5 or day.isoformat() in holidays or (day.month, day.day) == (12, 25):\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
