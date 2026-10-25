#!/usr/bin/env bash
# Record the worktree as the model receives it, in the grading stage given as the one argument:
# the file list, each file's content hash, and `git status`. The setup runs it, and the runner
# runs it again from the stage once the arm's install is in, so that what the install wrote is
# part of the baseline and not counted as the model's edit.
set -euo pipefail
stage="${1:?usage: baseline.sh <grading-stage>}"
if command -v sha256sum >/dev/null 2>&1; then checker="sha256sum"; else checker="shasum -a 256"; fi
find . \( -path ./.git -o -name __pycache__ \) -prune -o -type f -print | sort > "$stage/checks/baseline-files"
xargs $checker < "$stage/checks/baseline-files" > "$stage/checks/baseline-hashes"
git status --porcelain --untracked-files=all > "$stage/checks/baseline-status"
