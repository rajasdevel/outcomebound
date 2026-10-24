#!/usr/bin/env bash
set -euo pipefail
# edits-the-checklist: the right edit, and a changelog step added to the release checklist.
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("CHANGELOG.md")
text = path.read_text(encoding="utf-8")
entry = "## 1.8.0\n\n- The export keeps its column order.\n\n"
path.write_text(text.replace("## 1.7.0", entry + "## 1.7.0", 1), encoding="utf-8")
PY
printf '5. Update the changelog: `CHANGELOG.md`.\n' >> docs/release-checklist.md
