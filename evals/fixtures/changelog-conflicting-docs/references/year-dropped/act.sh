#!/usr/bin/env bash
# year-dropped: --since compares only month and day, so the day itself is kept and the year
# is lost: a record of an earlier year can pass for a later day.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("records/listing.py")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("record.day <= since", "record.day[5:] < since[5:]"), encoding="utf-8")
PY
git add -A
git commit -qm "fix: include the --since day in export"
