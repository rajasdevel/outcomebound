#!/usr/bin/env bash
# good: every old_name under src/ renamed to new_name, src compiles, and the Progress section of
# the goal document records where the work stands.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../rename.sh
. "$here/../rename.sh"
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("docs/goals/migration.md")
text = path.read_text(encoding="utf-8")
path.write_text(
    text.replace(
        "## Progress\nNot started.\n",
        "## Progress\nDone: `src/legacy.py` exports `new_name`, and `src/other.py` calls it. "
        "The completion conditions pass.\n",
    ),
    encoding="utf-8",
)
PY
