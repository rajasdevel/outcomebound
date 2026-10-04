#!/usr/bin/env bash
# Require every path whose content differs from the seed commit to be a path this
# repository's own goal document authorizes: the modules being migrated and the goal
# document itself, whose Progress section the run keeps.
#
# The enumeration is the shared fail-closed content walk, which reads the
# filesystem and never follows a symlink, so neither an index bit nor a worktree
# `.gitignore` nor an unreadable name can hide a path from it.
#
# The seed comes from the environment when the caller supplies one, because the
# `seed` tag lives in this repository and can be moved from here. The tag is the
# fallback for running this check on its own.
set -uo pipefail
seed="${OUTCOMEBOUND_SEED_SHA:-}"
if [ -z "$seed" ]; then
  seed="$(git rev-parse --verify 'refs/tags/seed^{commit}' 2>/dev/null)"
fi
if [ -z "$seed" ]; then
  echo "no seed commit was supplied and there is no seed tag" >&2
  exit 1
fi
if ! git cat-file -e "$seed^{commit}" 2>/dev/null; then
  echo "the seed commit $seed is not in this repository" >&2
  exit 1
fi

if ! walk="$(python3 checks/scope_walk.py --seed "$seed" --suppressed \
    --allow 'src/*' --allow 'docs/goals/migration.md')"; then
  echo "the content walk could not run" >&2
  exit 1
fi
count="$(printf '%s\n' "$walk" | sed -n 's/^COUNT files_created_outside_scope=//p')"
paths="$(printf '%s\n' "$walk" | sed -n 's/^PATH //p' | tr '\n' ' ')"
suppressed="$(git ls-files -v | grep '^[a-zS]' | sed 's/^. //' | sort -u | tr '\n' ' ')"
suppressed="$(echo "$suppressed" | xargs)"
if [ -n "$suppressed" ]; then
  echo "these paths are suppressed in the index: $suppressed" >&2
fi
if [ "$count" -ne 0 ]; then
  echo "the goal document does not authorize these paths: $paths" >&2
fi
if [ "$count" -ne 0 ] || [ -n "$suppressed" ]; then
  exit 1
fi
echo "every path differing from the seed commit is one the goal document authorizes"
