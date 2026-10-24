#!/usr/bin/env bash
# missing-home: the good fix, then the home page removed from content/ and site/: the rest
# of the site still links to index.html.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

for name in ("content/_data.json", "content/faq.md"):
    path = Path(name)
    path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
python3 -I -B build.py >/dev/null
rm content/index.md site/index.html
