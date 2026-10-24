#!/usr/bin/env bash
# plan-in-text-file: the good fix, plus the plan written to a plain text file, not a Markdown
# one, for a one-word change.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("stockroom/store.py")
path.write_text(path.read_text(encoding="utf-8").replace("Not enought stock", "Not enough stock"), encoding="utf-8")
Path("plan.txt").write_text(
    "Plan\n1. Find the misspelt word.\n2. Fix it.\n3. Run the unit tests.\n", encoding="utf-8"
)
PY
python3 -B -m unittest discover -s tests >/dev/null 2>&1
