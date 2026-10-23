#!/usr/bin/env bash
# edit-html: CONTRIBUTING.md followed: the served page edited by hand, content/ left as it was.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("site/install.html")
path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
