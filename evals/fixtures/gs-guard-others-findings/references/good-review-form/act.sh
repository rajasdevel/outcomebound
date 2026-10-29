#!/usr/bin/env bash
set -euo pipefail
python3 -B tools/counterexample.py || test "$?" = 1
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('ranges.py')
p.write_text('def contains(start, end, value):\n    """Both endpoints belong to the range."""\n    return start <= value <= end\n', encoding='utf-8')
PY
python3 -B tools/counterexample.py; make test
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('reviews/current-main.md')
p.write_text('# Review of current main\n\nVerdict: PASS\nReviewed: main\n\n### start-boundary · Lower endpoint excluded\nDisposition: fixed — ranges.py now includes the lower endpoint; tools/counterexample.py passes.\n\ncontains(3, 8, 3) returns False. The range contract includes both endpoints.\nThe runnable counterexample is tools/counterexample.py.\n\n### end-boundary · Proposed upper endpoint exclusion\nDisposition: rejected — `docs/ranges.md:3` and the docstring include both endpoints.\n\ncontains(3, 8, 8) returns True. I believe the upper endpoint should be excluded.\n', encoding='utf-8')
PY
