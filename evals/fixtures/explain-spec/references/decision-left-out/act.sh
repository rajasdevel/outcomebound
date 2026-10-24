#!/usr/bin/env bash
# good: the design and the code are read; nothing is changed.
set -euo pipefail
cat docs/specs/notify/design.md >/dev/null
cat notify.py >/dev/null
git status --short >/dev/null
