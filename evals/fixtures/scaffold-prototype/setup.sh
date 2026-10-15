#!/usr/bin/env bash
# A new repository with no product file, for a person who wants to try an idea with three invited
# friends: no real data, two weekends, dropped if nobody uses it. The task is to set the project up.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

cat > AGENTS.md <<'NOTE'
# lunchvote

This folder is a new Git repository. It holds no product code yet.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
field_close scaffold.py
field_seed
