#!/usr/bin/env bash
# validation-added: the docstring fixed, and a new rule added to the code: clamp now raises when low is above high.
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

path = Path('clamp.py')
text = path.read_text(encoding="utf-8")
old = '    return max(low, min(value, high))'
new = '    if low > high:\n        raise ValueError("low must not be above high")\n    return max(low, min(value, high))'
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
