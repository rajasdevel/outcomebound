# Shared by the references: the rename the goal document asks for, done in src/.
python3 -I -B - <<'PY'
from pathlib import Path

for path in Path("src").glob("*.py"):
    path.write_text(path.read_text(encoding="utf-8").replace("old_name", "new_name"), encoding="utf-8")
PY
