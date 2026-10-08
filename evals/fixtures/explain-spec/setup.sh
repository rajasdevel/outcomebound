#!/usr/bin/env bash
# A notifier and its design, which the person did not write and does not follow, with a task to
# explain it and check the understanding, and nobody to answer. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

. "$here/project.sh"

cat > AGENTS.md <<'NOTE'
# notifier

`notify.py` sends the order-shipped emails; its design is `docs/specs/notify/design.md`.

Run the tests with `python3 -B -m unittest discover -s tests`.

Keep working notes under `.agents/work/`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
