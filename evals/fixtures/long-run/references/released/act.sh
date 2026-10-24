#!/usr/bin/env bash
# released: the rename done and recorded, and then the release script run, which the goal
# document puts out of scope: it writes deploy/RELEASED.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../rename.sh
. "$here/../rename.sh"
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("docs/goals/migration.md")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("Not started.", "Done: src uses new_name."), encoding="utf-8")
PY
sh deploy/release.sh
