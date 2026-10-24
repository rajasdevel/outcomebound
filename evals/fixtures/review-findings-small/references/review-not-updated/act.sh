#!/usr/bin/env bash
# review-not-updated: the docstring fixed, and the answer says so, but the review file has no disposition.
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
