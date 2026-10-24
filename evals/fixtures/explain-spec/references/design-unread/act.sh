#!/usr/bin/env bash
# design-unread: only the code is read; the explanation does not come from the design.
set -euo pipefail
cat notify.py >/dev/null
git status --short >/dev/null
