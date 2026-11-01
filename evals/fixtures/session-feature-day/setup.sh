#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
# shellcheck source=../session/chatsvc/extend.sh
. "$repo/evals/fixtures/session/chatsvc/extend.sh"
# shellcheck source=../replica/chatsvc/finish.sh
. "$repo/evals/fixtures/replica/chatsvc/finish.sh"
printf '.remotes/\n' >> .git/info/exclude
git init --bare -q .remotes/origin.git
git --git-dir=.remotes/origin.git config core.logAllRefUpdates true
git remote add origin "$PWD/.remotes/origin.git"
cp "$stage/checks/note.py" "$stage/checks/replica_note.py"
cp "$here"/checks/*.py "$stage/checks/"
cp "$here/session.json" "$here/person.json" "$stage/checks/"
cp "$repo/evals/session_protocol.py" "$repo/evals/fixtures/session/common/"*.py "$stage/checks/"
python3 -I -B "$stage/checks/long_checks.py" record
python3 -I -B "$stage/checks/delivered.py" "$stage/checks/seed-checks"

cp "$here/session.json" "$stage/checks/session.json"

python3 -I -B "$repo/evals/fixtures/session/common/instrument.py" hooks
