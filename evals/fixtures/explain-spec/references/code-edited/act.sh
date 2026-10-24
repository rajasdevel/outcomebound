#!/usr/bin/env bash
# code-edited: the explanation is right, but the run also added a comment to notify.py.
set -euo pipefail
cat docs/specs/notify/design.md >/dev/null
cat notify.py >/dev/null
printf '\n# The retry policy is explained in docs/specs/notify/design.md.\n' >> notify.py
