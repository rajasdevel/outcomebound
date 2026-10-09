#!/usr/bin/env bash
# An empty Git repository: a project note, the core skill and nothing else, and a request for a
# script that one person needs for their own photos. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > AGENTS.md <<'NOTE'
# photo tools

This folder is a new Git repository. It holds no code yet.

Keep working files under `.agents/work/`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p checks
cp "$repo/evals/graders/new_project.py" checks/

. "$here/../skills-close/close.sh"
