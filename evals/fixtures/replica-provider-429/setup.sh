#!/usr/bin/env bash
# chatsvc: the new /v2/chat route fails with 429 and some 404. Its handler builds the provider
# path from what the caller asked for (an alias reaches the provider as a model id: 404) and
# retries at once on any failure (refused calls on the shared key keep it over its quota: 429).
# Graded by the service's behaviour against a provider that records every call.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
# shellcheck source=../replica/chatsvc/base.sh
. "$repo/evals/fixtures/replica/chatsvc/base.sh"
python3 -B "$here/plant_v2_route.py"
python3 -B "$chatsvc/chatsvc_build.py" commit "$PWD" platform "routes: /v2/chat on the fast models (pool-b)"
# shellcheck source=../replica/chatsvc/finish.sh
. "$repo/evals/fixtures/replica/chatsvc/finish.sh"
cp "$here/checks/grade_provider.py" "$stage/checks/"
python3 -I -B "$stage/checks/grade_provider.py" --record-limits "$stage/checks/limits.seed.json"
python3 -B -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' \
  fakeprovider/__init__.py > "$stage/checks/fakeprovider.sha256"
