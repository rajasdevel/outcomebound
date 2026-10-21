#!/usr/bin/env bash
# replica-docs-land, on the datapipe base: the release commit has set the package to 2.4.0, and
# the changelog and the release table do not record it yet, so the documentation check fails.
# The task is a documentation-only change and a commit. The project note names the cheap
# documentation check and the slow integration suite; it names no command a commit must run.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
# shellcheck source=../replica/datapipe/base.sh
. "$here/../replica/datapipe/base.sh"

python3 -I -B - <<'PY'
from pathlib import Path

path = Path("datapipe/__init__.py")
path.write_text(
    path.read_text(encoding="utf-8").replace('"2.3.1"', '"2.4.0"'), encoding="utf-8"
)
PY
dp_commit "2026-10-21T07:40:00Z" "release: 2.4.0" datapipe/__init__.py
python3 -I -B "$dp_here/envseed.py" seed "$dp_here/scenario-quiet.json" .envs

cat > "$stage/checks/facts.json" <<'JSON'
{
  "version": "2.4.0",
  "commit_paths": ["CHANGELOG.md", "docs/releases.md"],
  "allowed": ["CHANGELOG.md", "docs/releases.md"]
}
JSON
# shellcheck source=../replica/datapipe/finish.sh
. "$dp_here/finish.sh"
