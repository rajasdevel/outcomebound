#!/usr/bin/env bash
# record release 2.4.0 in the changelog and in the release table
python3 -B - <<'PY'
from pathlib import Path

p = Path("CHANGELOG.md")
head = "## Unreleased\n\n"
p.write_text(p.read_text().replace(head, head + "## 2.4.0 - 2026-10-21\n\n", 1))
p = Path("docs/releases.md")
row = "| 2.4.0 | 2026-10-21 | Failed jobs retry. |\n"
p.write_text(p.read_text().replace("| 2.3.1 |", row + "| 2.3.1 |", 1))
PY
python3 -B tools/docs_check.py >/dev/null
git commit -qam 'docs: 2.4.0'
