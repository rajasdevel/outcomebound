#!/usr/bin/env bash
# incomplete: the install page gets a literal 3.0.0 in place of the shared snippet; quickstart and
# the FAQ still show 2.4.1. The site is rebuilt.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("content/install.md")
text = path.read_text(encoding="utf-8")
literal = "Install the current release with pip:\n\n```\npip install examplectl==3.0.0\n```"
path.write_text(text.replace("{{> install-command}}", literal), encoding="utf-8")
PY
python3 -I -B build.py >/dev/null
