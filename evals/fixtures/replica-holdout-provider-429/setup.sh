#!/usr/bin/env bash
# Held out. chatsvc: bulk embedding requests fail with 400 and 429 since one commit. Graded by
# the route's behaviour against a provider that records every call.
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
python3 -B "$here/plant_embed_batches.py"
python3 -B "$chatsvc/chatsvc_build.py" commit "$PWD" platform "embed: one provider call per request"
# shellcheck source=../replica/chatsvc/finish.sh
. "$repo/evals/fixtures/replica/chatsvc/finish.sh"
cp "$repo/evals/fixtures/replica-provider-429/checks/grade_provider.py" "$here/checks/grade_embed.py" \
  "$stage/checks/"
python3 -I -B "$stage/checks/grade_provider.py" --record-limits "$stage/checks/limits.seed.json"
python3 -B -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' \
  fakeprovider/__init__.py > "$stage/checks/fakeprovider.sha256"
