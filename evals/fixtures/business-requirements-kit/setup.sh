#!/usr/bin/env bash
# The business requirements kit, pasted with two call transcripts by a person who wants the draft
# now. The workspace holds nothing to build: the answer is the card. The sources are copied into
# the protected checks so the grader can look every quote up. Run it under the kernel-off arm
# (`--arm none`): the kit text under test is in the prompt, as a business owner pastes it into a
# plain assistant.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > AGENTS.md <<'NOTE'
# requirements card

Nothing is built in this folder. The person pastes a kit and their material, and the answer is
the requirements card. Do not write files for the answer.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p checks/sources
cp "$here"/sources/*.txt checks/sources/

. "$here/../skills-close/close.sh"
