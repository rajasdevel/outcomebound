# The one-line fix: divmod of the absolute value, the sign written once.
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("ledger/display.py")
path.write_text(
    path.read_text(encoding="utf-8").replace("divmod(cents, 100)", "divmod(abs(cents), 100)"),
    encoding="utf-8",
)
PY
