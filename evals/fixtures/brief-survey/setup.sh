#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
corelib="$here/../replica/corelib"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
# shellcheck source=../replica/chatsvc/base.sh
. "$here/../replica/chatsvc/base.sh"
python3 -I -B "$here/../brief/plant.py" "$here" "$stage/checks"
python3 -I -B "$repo/evals/fixtures/session/common/instrument.py"
bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude
git add -A
GIT_AUTHOR_DATE="2026-10-21T12:00:00Z" GIT_COMMITTER_DATE="2026-10-21T12:00:00Z" \
  git commit -qm "fixture: bounded work and its contract"
git tag seed
cp "$here/brief_survey.py" "$stage/checks/brief.py"
python3 -I -B - "$here/facts.json" "$stage/checks/facts.json" <<'FACTS'
import json
import subprocess
import sys
from pathlib import Path

facts = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
facts["refs"] = subprocess.check_output(["git", "show-ref"], text=True).strip()
Path(sys.argv[2]).write_text(json.dumps(facts), encoding="utf-8")
FACTS
cp "$here/expected.json" "$stage/checks/expected.json"

cp "$repo/evals/session_protocol.py" "$repo/evals/fixtures/session/common/"*.py "$stage/checks/"

python3 -I -B "$repo/evals/fixtures/session/common/instrument.py" hooks
