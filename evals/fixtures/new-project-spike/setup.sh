#!/usr/bin/env bash
# An empty Git repository with a sample of 40 receipts as text recognition read them and the real
# date of each. The date is missing from the text of 18 of the 40, so no reader of the text gets
# the date right on more than 22. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > AGENTS.md <<'NOTE'
# receipt dates

This folder is a new Git repository. It holds no code yet, and a sample in `sample/`.

Keep working files under `.agents/work/`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p sample checks
cp "$here/sample/receipts.txt" "$here/sample/dates.csv" sample/
cp "$repo/evals/graders/new_project.py" checks/

. "$here/../skills-close/close.sh"
