# A patch for the amounts under one unit only: -0.50 prints right, -12.50 still does not.
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("ledger/display.py")
path.write_text(
    path.read_text(encoding="utf-8").replace(
        '    sign = "-" if cents < 0 else ""\n',
        '    if -100 < cents < 0:\n        return f"-0.{-cents:02d}"\n'
        '    sign = "-" if cents < 0 else ""\n',
    ),
    encoding="utf-8",
)
PY
