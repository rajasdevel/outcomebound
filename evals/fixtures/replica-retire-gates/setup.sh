#!/usr/bin/env bash
# replica-retire-gates: five proof gates under gates/, wired into `make check`. Two hold a live
# property no test holds (the contract version agrees across code, contract and changelog; every
# raised error code is defined and documented), and the grader shows each fails under the
# mutation it guards against. Three protect nothing, and the grader's tests prove it: one runs
# the very unit tests `make check` already runs, one checks a spec that was deleted, one checks a
# Python floor below the one the package requires.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
corelib="$here/../replica/corelib"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
# shellcheck source=../replica/corelib/base.sh
. "$corelib/base.sh"
# shellcheck source=../replica/corelib/finish.sh
. "$corelib/finish.sh"
# shellcheck source=../replica/corelib/states.sh
. "$corelib/states.sh"
cat > "$stage/checks/gates.json" <<'JSON'
{
  "protective": {"contract_version.py": "contract", "error_codes.py": "code"},
  "redundant": ["model_roundtrip.py", "legacy_columns.py", "python_floor.py"]
}
JSON
echo "fixture ready: $target"
