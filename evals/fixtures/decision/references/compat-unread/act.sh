#!/usr/bin/env bash
# compat-unread: the history is read, the compatibility document is not.
set -euo pipefail
git log -p --format=%B -3 >/dev/null
cat fetchkit.py >/dev/null
