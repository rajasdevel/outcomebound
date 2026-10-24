#!/usr/bin/env bash
# snippet-only: the shared value moved and the site rebuilt; the FAQ's own 2.4.1 missed.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("content/_data.json")
path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
python3 -I -B build.py >/dev/null
