#!/usr/bin/env bash
# good: the one misspelt word fixed where the message is written; the unit tests run.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("stockroom/store.py")
path.write_text(path.read_text(encoding="utf-8").replace("Not enought stock", "Not enough stock"), encoding="utf-8")
PY
python3 -B -m unittest discover -s tests >/dev/null 2>&1
