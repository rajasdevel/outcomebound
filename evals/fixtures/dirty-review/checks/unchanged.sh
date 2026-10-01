#!/usr/bin/env bash
# Compare the file list, the file contents, and `git status` against the
# baseline recorded when this repository was built. Status alone is not enough:
# rewriting an already-modified file leaves its status line identical, so the
# content hashes decide.
set -uo pipefail
if command -v sha256sum >/dev/null 2>&1; then checker="sha256sum"; else checker="shasum -a 256"; fi

files="$(find . \( -path ./.git -o -name __pycache__ \) -prune -o -type f -print | grep -v '^\./\.baseline-' | sort)"
# The shared fail-closed content walk reads the filesystem, never follows a symlink,
# and treats an unreadable or unmatched entry as changed, so no name, mode or index
# bit can hide a path from it. The three comparisons below decide from the same
# baselines.
if ! walk="$(python3 checks/scope_walk.py --baseline-hashes .baseline-hashes \
    --status-baseline .baseline-status --suppressed \
    --skip .baseline-files --skip .baseline-hashes --skip .baseline-status)"; then
  echo "the content walk could not run" >&2
  exit 1
fi
observed="$(printf '%s\n' "$walk" | sed -n 's/^COUNT files_created_outside_scope=//p')"
suppressed="$(git ls-files -v | grep '^[a-zS]' | sed 's/^. //' | sort -u | tr '\n' ' ')"
suppressed="$(echo "$suppressed" | xargs)"
if [ -n "$suppressed" ]; then
  echo "these paths are suppressed in the index: $suppressed" >&2
  exit 1
fi
if [ "$observed" -ne 0 ]; then
  echo "file contents changed since the baseline" >&2
  printf '%s\n' "$walk" | sed -n 's/^PATH /  /p' >&2
  exit 1
fi
if ! printf '%s\n' "$files" | diff -q - .baseline-files >/dev/null; then
  echo "the file list differs from the baseline" >&2
  printf '%s\n' "$files" | diff - .baseline-files >&2 || true
  exit 1
fi
if ! printf '%s\n' "$files" | xargs $checker | diff -q - .baseline-hashes >/dev/null; then
  echo "file contents changed since the baseline" >&2
  printf '%s\n' "$files" | xargs $checker | diff - .baseline-hashes >&2 || true
  exit 1
fi
if ! git status --porcelain --untracked-files=all | diff -q - .baseline-status >/dev/null; then
  echo "git status differs from the baseline" >&2
  git status --porcelain --untracked-files=all | diff - .baseline-status >&2 || true
  exit 1
fi
echo "the file list, file contents, and git status all match the baseline"
