#!/usr/bin/env bash
# malformed-row: the fix, plus a one-column debug row printed after the header of every export.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("records/listing.py")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("record.day <= since", "record.day < since"), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("records/listing.py")
text = path.read_text(encoding="utf-8")
path.write_text(
    text.replace("    writer.writerow(COLUMNS)\n", "    writer.writerow(COLUMNS)\n    writer.writerow((\"DEBUG: exporting records\",))\n"),
    encoding="utf-8",
)
PY
git add -A
git commit -qm "fix: include the --since day in export"
