#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('ledger/display.py')
t = p.read_text(encoding='utf-8')
if t.count('divmod(cents, 100)') != 1:
    raise SystemExit('replacement must match once')
p.write_text(t.replace('divmod(cents, 100)', 'divmod(abs(cents), 100)'), encoding='utf-8')
PY
make unit
