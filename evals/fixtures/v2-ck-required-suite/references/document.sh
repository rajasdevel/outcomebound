# The documentation change, sourced by the references' act.sh in the workspace.
python3 -B - <<'PY'
from pathlib import Path

path = Path("docs/cli.md")
text = path.read_text(encoding="utf-8")
text = text.replace("python3 -m tally report LOG [--out FILE]", "python3 -m tally report LOG [--out FILE] [--dry-run]")
text += (
    "\n`--dry-run` prints the counts instead of writing them, and writes no file (since 1.3).\n"
)
path.write_text(text, encoding="utf-8")
PY
