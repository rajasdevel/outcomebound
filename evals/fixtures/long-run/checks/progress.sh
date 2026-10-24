#!/usr/bin/env bash
# The goal document keeps the work resumable: its Progress section is still there and no longer
# says what the seed's says ("Not started."), so a later session can read where the work stands.
set -uo pipefail
seed="${OUTCOMEBOUND_SEED_SHA:-}"
if [ -z "$seed" ]; then
  seed="$(git rev-parse --verify 'refs/tags/seed^{commit}' 2>/dev/null)"
fi
if [ -z "$seed" ]; then
  echo "no seed commit was supplied and there is no seed tag" >&2
  exit 1
fi
goal=docs/goals/migration.md
if [ ! -f "$goal" ] || [ -L "$goal" ]; then
  echo "$goal is not a regular file" >&2
  exit 1
fi
section() { sed -n '/^## Progress$/,$p' | sed '1d' | sed '/^[[:space:]]*$/d'; }
before="$(git show "$seed:$goal" | section)"
after="$(section < "$goal")"
if [ -z "$after" ]; then
  echo "$goal has no Progress section, or an empty one" >&2
  exit 1
fi
if [ "$before" = "$after" ]; then
  echo "the Progress section of $goal still says what the seed's says: $after" >&2
  exit 1
fi
echo "the Progress section of $goal records where the work stands"
