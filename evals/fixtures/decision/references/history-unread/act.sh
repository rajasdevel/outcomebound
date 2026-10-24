#!/usr/bin/env bash
# history-unread: the compatibility document is read, the history is not.
set -euo pipefail
cat docs/compatibility.md >/dev/null
cat fetchkit.py >/dev/null
