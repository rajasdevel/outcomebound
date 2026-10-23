#!/usr/bin/env bash
# A one-file repository with a misspelt greeting, for evals/selftest.py's own tests. Its graders
# go to the grading stage, never into the workspace.
set -euo pipefail
case "${1:-}" in
-h | --help)
	printf '%s\n' "usage: setup.sh <dir> <grading-stage>" "Builds the tiny fixture's repository in <dir> and its graders in <grading-stage>."
	exit 0
	;;
esac
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cp "$here/check.py" "$stage/checks/check.py"
cd "$target"
printf 'helo\n' > greeting.txt
git init -q
git add greeting.txt
GIT_AUTHOR_DATE=2026-01-01T00:00:00Z GIT_COMMITTER_DATE=2026-01-01T00:00:00Z \
  git -c user.name=fixture -c user.email=fixture@example.invalid commit -q -m seed
git tag seed
