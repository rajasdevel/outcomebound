# Sourced by the references of this fixture: `fix <condition>` replaces the refusal test in
# `take` with the condition given, with the python the setup used to plant the defect.
fix() {
  python3 -I -B - "$1" <<'PY'
import sys
from pathlib import Path

path = Path("stockroom/store.py")
text = path.read_text(encoding="utf-8")
assert "if qty >= have:" in text
path.write_text(text.replace("if qty >= have:", sys.argv[1]), encoding="utf-8")
PY
}
