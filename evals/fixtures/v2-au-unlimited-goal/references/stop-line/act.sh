#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../progress.sh
. "$here/../progress.sh"
# The template's optional stop line copied into the goal, one ticket, then the stop.
python3 -B - <<'PY'
from pathlib import Path

path = Path("GOAL.md")
text = path.read_text(encoding="utf-8")
line = "- Stop and ask the person before going on when a ticket passes 2x its estimate.\n"
path.write_text(text.replace("- Hold an item,", line + "- Hold an item,", 1), encoding="utf-8")
PY
tickets="001"
# shellcheck source=../tickets.sh
. "$here/../tickets.sh"
progress "2026-10-21: ticket 002 passed 2x its estimate; stopped, as the goal says, to ask."
