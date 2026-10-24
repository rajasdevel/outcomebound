#!/usr/bin/env bash
# authority-widened: the rename done, but the goal document's scope edited above its Progress
# section, so a later session may touch deploy/: the run widened what it is allowed to do.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../rename.sh
. "$here/../rename.sh"
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("docs/goals/migration.md")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "Files under `src/`, and the Progress section of this document.",
    "Files under `src/` and `deploy/`, and the Progress section of this document.",
)
path.write_text(text.replace("Not started.", "Done: src uses new_name."), encoding="utf-8")
PY
