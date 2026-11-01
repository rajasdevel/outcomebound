#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('app.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("TITLE = 'Weekly summary'\nFOOTER = 'Draft copy'\n\n\ndef format_subject(name):\n    return f'{TITLE}: {name}'\n", encoding='utf-8')
PY
python3 -B tools/inventory.py
