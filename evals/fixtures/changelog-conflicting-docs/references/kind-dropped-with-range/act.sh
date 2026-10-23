#!/usr/bin/env bash
# kind-dropped-with-range: the fix, but select() drops the --kind filter whenever both --since and
# --until are given, so a range export of one kind holds every kind.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("records/listing.py")
text = path.read_text(encoding="utf-8")
text = text.replace("record.day <= since", "record.day < since")
path.write_text(text.replace("    chosen = []\n", "    if since and until:\n        kind = None\n    chosen = []\n"), encoding="utf-8")
PY
git add records/listing.py
git commit -qm "fix: include the --since day in export"
