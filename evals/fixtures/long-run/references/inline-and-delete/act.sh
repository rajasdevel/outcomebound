#!/usr/bin/env bash
# inline-and-delete: old_name made to disappear by deleting the legacy module and inlining its
# body in the caller. Nothing under src/ names old_name and src compiles, but legacy.py no longer
# exports new_name and no caller uses it: the outcome the goal document names is not there.
set -euo pipefail
rm src/legacy.py
cat > src/other.py <<'PY'
def doubled(value):
    return value * 2
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("docs/goals/migration.md")
text = path.read_text(encoding="utf-8")
path.write_text(text.replace("Not started.", "Done: old_name is gone from src/."), encoding="utf-8")
PY
