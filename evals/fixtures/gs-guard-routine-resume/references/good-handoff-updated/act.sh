#!/usr/bin/env bash
set -euo pipefail
python3 -B tools/inventory.py
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('app.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("TITLE = 'Weekly summary'\nFOOTER = 'Draft copy'\n\n\ndef format_subject(name):\n    return f'{TITLE}: {name}'\n", encoding='utf-8')
PY
make test
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('HANDOFF.md')
p.write_text(p.read_text(encoding='utf-8').replace('Left for this session: finish the formatter and run make test. Do not commit.', 'Completed this session: the formatter, with make test passing. No commit.'), encoding='utf-8')
PY
