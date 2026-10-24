#!/usr/bin/env bash
set -euo pipefail
# wrong-place: the 1.8.0 section added below the 1.7.0 one.
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("CHANGELOG.md")
path.write_text(path.read_text(encoding="utf-8") + "\n## 1.8.0\n\n- The export keeps its column order.\n", encoding="utf-8")
PY
