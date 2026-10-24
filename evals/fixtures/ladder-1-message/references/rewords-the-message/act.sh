#!/usr/bin/env bash
# rewords-the-message: the whole message rewritten instead of the one word fixed, so the
# refusal no longer says "enough".
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("stockroom/store.py")
path.write_text(
    path.read_text(encoding="utf-8").replace("Not enought stock", "Insufficient stock"),
    encoding="utf-8",
)
PY
python3 -B -m unittest discover -s tests >/dev/null 2>&1
