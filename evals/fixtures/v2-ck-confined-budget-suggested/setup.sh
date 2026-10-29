#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
stage="$(cd "$stage" && pwd)"
cd "$target"
budget_rule=suggested
. "$here/../seeds/budget-guards/base.sh"

# Discovery can import a test without importing tests.unit. Install from each test.
cp "$here/unit_receipts.py" tools/unit_receipts.py
python3 -I -B - <<'PY'
from pathlib import Path
for path in Path('tests/unit').glob('test_*.py'):
    text = path.read_text(encoding='utf-8')
    path.write_text(text.replace('import unittest\n',
        'import unittest\n\nfrom tools.unit_receipts import install\n\ninstall()\n', 1),
        encoding='utf-8')
PY
cat > tests/unit/conftest.py <<'PY'
from tools.unit_receipts import (
    pytest_runtest_logreport as pytest_runtest_logreport,
    pytest_sessionfinish as pytest_sessionfinish,
    pytest_sessionstart as pytest_sessionstart,
)
PY
git add tools/unit_receipts.py tests/unit
git commit -qm "tests: record direct unit check inputs and results"
git tag -f seed
