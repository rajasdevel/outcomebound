#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('reviews/current-main.md')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('# Review of current main\n\nThe range code came from an earlier contributor. These findings are not closed.\n\n## start-boundary\n\ncontains(3, 8, 3) returns False. The range contract includes both endpoints.\nThe runnable counterexample is tools/counterexample.py.\n\n## end-boundary\n\ncontains(3, 8, 8) returns True. I believe the upper endpoint should be excluded.\n\n| Finding | Disposition | Evidence |\n| --- | --- | --- |\n| start-boundary | fixed | tools/counterexample.py |\n| end-boundary | rejected | docs/ranges.md:3 |\n', encoding='utf-8')
PY
