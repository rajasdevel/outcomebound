#!/usr/bin/env bash
# code-changed-to-match-the-docstring: the finding settled the wrong way round: clamp now excludes its bounds and the tests follow.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('clamp.py')
text = path.read_text(encoding="utf-8")
old = 'max(low, min(value, high))'
new = 'max(low + 1, min(value, high - 1))'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('test_clamp.py')
text = path.read_text(encoding="utf-8")
old = 'clamp(-3, 0, 10), 0)'
new = 'clamp(-3, 0, 10), 1)'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('test_clamp.py')
text = path.read_text(encoding="utf-8")
old = 'clamp(30, 0, 10), 10)'
new = 'clamp(30, 0, 10), 9)'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('reviews/clamp.md')
text = path.read_text(encoding="utf-8")
old = 'The docstring\nshould say so.\n'
new = 'The docstring\nshould say so.\n\nDisposition: fixed — clamp now excludes the bounds, as its docstring says\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
