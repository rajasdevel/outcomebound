#!/usr/bin/env bash
# The notifier of the explain-spec fixture and a task that is one question about its design, from
# the person who wrote it. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

. "$here/../explain-spec/project.sh"

cat > AGENTS.md <<'NOTE'
# notifier

`notify.py` sends the order-shipped emails; its design is `docs/specs/notify/design.md`.

Run the tests with `python3 -B -m unittest discover -s tests`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
