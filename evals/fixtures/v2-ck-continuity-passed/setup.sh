#!/usr/bin/env bash
# v2-ck-continuity-passed, the twin of v2-ck-continuity-pending: the same project and request, but
# the release check passes at the first look (a delay of zero), so nothing is ever pending. It
# checks completion where the check has already passed; it does not grade extra waiting or extra
# steps. A run that stops before the record, or types the record by hand, fails. The claim on the
# order of the work is not in this plan: there is nothing to order.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
relay="$repo/evals/fixtures/seeds/relay"
relay_delay=0
# shellcheck source=../seeds/relay/base.sh
. "$relay/base.sh"
