#!/usr/bin/env bash
# global-replace: every 2.4.1 under content/ replaced, the history pages included; site rebuilt.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

for path in Path("content").rglob("*"):
    if path.is_file():
        path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
python3 -I -B build.py >/dev/null
