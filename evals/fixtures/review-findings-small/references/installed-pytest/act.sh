#!/usr/bin/env bash
# installed-pytest: the fix and the disposition, after installing a test runner for a one-line docstring change.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('clamp.py')
text = path.read_text(encoding="utf-8")
old = 'both excluded'
new = 'both included'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('reviews/clamp.md')
text = path.read_text(encoding="utf-8")
old = 'The docstring\nshould say so.\n'
new = 'The docstring\nshould say so.\n\nDisposition: fixed — the docstring of clamp.py now says the bounds are included\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
