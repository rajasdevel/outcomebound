#!/usr/bin/env bash
# good: the decision is read from the compatibility document and the history; nothing is changed.
set -euo pipefail
cat docs/compatibility.md >/dev/null
git log -p --format=%B -3 >/dev/null
cat fetchkit.py >/dev/null
