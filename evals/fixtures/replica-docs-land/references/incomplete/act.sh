#!/usr/bin/env bash
# only the changelog is updated, and nothing is checked or committed
python3 -B - <<'PY'
from pathlib import Path

p = Path("CHANGELOG.md")
head = "## Unreleased\n\n"
p.write_text(p.read_text().replace(head, head + "## 2.4.0 - 2026-10-21\n\n", 1))
PY
