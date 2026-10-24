#!/usr/bin/env bash
# leftover-repro: the fix, and a repro script left in the repository.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('tally.py')
text = path.read_text(encoding="utf-8")
old = 'totl /'
new = 'total /'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
cat > repro.py <<'EOF'
from tally import mean

print(mean([2, 4, 9]))
EOF
