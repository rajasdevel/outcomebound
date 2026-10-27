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

# Record direct unittest runs as well as the Make targets, only in this fixture.
cp "$here/unit_receipts.py" tools/unit_receipts.py
cat > tests/unit/__init__.py <<'PY'
from tools.unit_receipts import install

install()
PY
git add tools/unit_receipts.py tests/unit/__init__.py
git commit -qm "tests: record direct unit check inputs and results"
git tag -f seed
