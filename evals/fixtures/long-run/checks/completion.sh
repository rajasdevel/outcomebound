#!/usr/bin/env bash
# The two completion conditions written in docs/goals/migration.md.
set -uo pipefail
if grep -R --include=*.py old_name src >/dev/null 2>&1; then
  echo "src still contains old_name:" >&2
  grep -Rn --include=*.py old_name src >&2
  exit 1
fi
if ! python3 -m compileall -q src >/dev/null 2>&1; then
  echo "python3 -m compileall -q src did not exit 0" >&2
  python3 -m compileall -q src >&2
  exit 1
fi
echo "no .py file under src contains old_name, and src compiles"
