#!/usr/bin/env bash
# more-retries: the lead followed: 20 retries in place of 5.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('internal/report/summary_test.go')
path.write_text(path.read_text(encoding='utf-8').replace('retry(t, 5,', 'retry(t, 20,'), encoding='utf-8')
PY
