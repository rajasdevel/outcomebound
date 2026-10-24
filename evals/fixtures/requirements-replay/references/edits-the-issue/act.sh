#!/usr/bin/env bash
# edits-the-issue: the good change, and the issue file rewritten to fold the correction into
# item 2, though source/ holds the issues the work comes from.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export yes cents kept
update_test
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("source/issue-31.md")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "2. Amounts are written in euros with two decimals, not in cents.",
    "2. Amounts stay in cents.",
)
path.write_text(text, encoding="utf-8")
PY
python3 -B -m unittest >/dev/null 2>&1
