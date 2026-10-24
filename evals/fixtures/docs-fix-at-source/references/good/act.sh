#!/usr/bin/env bash
# good: the version moved where the pages take it from (content/_data.json) and in the one FAQ
# answer that types it by hand; the history pages left alone; the site rebuilt.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

for name in ("content/_data.json", "content/faq.md"):
    path = Path(name)
    path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
python3 -I -B build.py >/dev/null
