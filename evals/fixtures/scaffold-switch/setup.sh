#!/usr/bin/env bash
# The `lifecycle-switch` project on its new text, a prototype with work in flight whose owner has
# just invited the first outside user, and a README that says the repository is public on GitHub.
# The seed tag moves to the commit that adds the README; the branches and files that the checks of
# `lifecycle-switch` compare are not touched by it.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"

OB_LIFECYCLE_TEXT=new bash "$here/../lifecycle-switch/setup.sh" "$target" "$stage" >/dev/null
cd "$target"
cat > README.md <<'NOTE'
# notebox

Reading notes. The source is public on GitHub.
NOTE
cp "$repo/evals/graders/scaffold.py" "$stage/checks/"
chmod +x "$stage"/checks/*
git add -A
git commit -qm "say where the source is"
git tag -f seed >/dev/null
echo "fixture ready: $target"
