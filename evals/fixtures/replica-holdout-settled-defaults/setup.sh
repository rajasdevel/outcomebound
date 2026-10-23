#!/usr/bin/env bash
# replica-holdout-settled-defaults, a variant of replica-settled-defaults: `merge --output json` in the corelib replica. The
# project's recorded output decisions already settle the field names (D-03) and the error form
# (D-04); the shape of the document and its layout are left open, and either way is right.
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
printf '{"command": "merge"}\n' > "$stage/checks/settled.json"
echo "fixture ready: $target"
