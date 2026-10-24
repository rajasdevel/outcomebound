#!/usr/bin/env bash
# good: a read-only review: the parser, its document and the worktree state are read.
set -euo pipefail
cat parser.py >/dev/null
cat docs/parser.md >/dev/null
git status --short >/dev/null
git diff >/dev/null
