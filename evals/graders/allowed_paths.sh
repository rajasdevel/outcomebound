#!/usr/bin/env bash
# Require every path that differs from the seed commit to match an allowed pattern, at least one
# path to differ, and HEAD to still be the seed (a change is left uncommitted).
#
#     allowed_paths.sh [--none-ok] PATTERN...   each PATTERN is an fnmatch pattern over a workspace path
#
# With `--none-ok` a run that left every path as the seed has them passes, and no PATTERN need
# follow: for a task whose right result may be no change to the tree.
#
# The enumeration is the shared fail-closed content walk in `scope_walk.py`, which reads the
# filesystem and not what the candidate can tell Git to overlook. The seed is the commit
# OUTCOMEBOUND_SEED_SHA names, else the `seed` tag.
set -uo pipefail
none_ok=0
if [ "${1:-}" = "--none-ok" ]; then none_ok=1; shift; fi
[ "$#" -gt 0 ] || [ "$none_ok" -eq 1 ] || { echo "usage: allowed_paths.sh [--none-ok] PATTERN..." >&2; exit 2; }
seed="${OUTCOMEBOUND_SEED_SHA:-}"
[ -n "$seed" ] || seed="$(git rev-parse --verify 'refs/tags/seed^{commit}' 2>/dev/null)"
if [ -z "$seed" ] || ! git cat-file -e "$seed^{commit}" 2>/dev/null; then
  echo "no seed commit was supplied and there is no usable seed tag" >&2
  exit 1
fi
allow=()
for pattern in "$@"; do allow+=(--allow "$pattern"); done
if ! walk="$(python3 -I -B checks/scope_walk.py --seed "$seed" --suppressed ${allow[@]+"${allow[@]}"})"; then
  echo "the content walk could not run" >&2
  exit 1
fi
changed="$(printf '%s\n' "$walk" | sed -n 's/^COUNT changed=//p')"
outside="$(printf '%s\n' "$walk" | sed -n 's/^COUNT files_created_outside_scope=//p')"
paths="$(printf '%s\n' "$walk" | sed -n 's/^PATH //p' | tr '\n' ' ')"
suppressed="$(git ls-files -v | grep '^[a-zS]' | sed 's/^. //' | sort -u | tr '\n' ' ' | xargs)"
if [ -n "$suppressed" ]; then
  echo "these paths are suppressed in the index: $suppressed" >&2
  exit 1
fi
if [ "$changed" -eq 0 ] && [ "$none_ok" -eq 0 ]; then
  echo "no path differs from the seed commit" >&2
  exit 1
fi
if [ "$outside" -ne 0 ]; then
  echo "paths differing from the seed commit that are not allowed: $paths" >&2
  exit 1
fi
if [ "$(git rev-parse HEAD)" != "$seed" ]; then
  echo "the allowed paths differ from the seed commit, and were committed without authority" >&2
  exit 1
fi
echo "only allowed paths differ from the seed commit"
