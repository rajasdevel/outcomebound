#!/usr/bin/env bash
set -euo pipefail
# The whole file restored, then the changes that were not the agent's typed back by hand.
git restore app/settings.py
python3 -B - <<'PY'
from pathlib import Path

path = Path("app/settings.py")
text = path.read_text(encoding="utf-8")
text = text.replace("ARCHIVE_DAYS = 30", "ARCHIVE_DAYS = 90")
text = text.replace('LOG_LEVEL = "INFO"\n', 'LOG_LEVEL = "DEBUG"\nLOG_FILE = "var/notifier.log"\n')
path.write_text(text, encoding="utf-8")
PY
