#!/usr/bin/env bash
# chatsvc: review the branch `webhook-retry` before the person merges it. The branch adds a
# provider usage webhook that charges the ledger for every delivery without looking at the
# event id, and answers 503 on a ledger error so the provider delivers again: a redelivered
# event is charged twice. Its own tests pass. HEAD stays on main.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
# shellcheck source=../replica/chatsvc/base.sh
. "$repo/evals/fixtures/replica/chatsvc/base.sh"
python3 -B "$here/plant_webhook_branch.py" "$stage/checks/review.json"
# shellcheck source=../replica/chatsvc/finish.sh
. "$repo/evals/fixtures/replica/chatsvc/finish.sh"
cp "$here/checks/grade_review.py" "$stage/checks/"
