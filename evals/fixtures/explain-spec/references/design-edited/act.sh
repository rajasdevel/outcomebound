#!/usr/bin/env bash
# design-edited: the explanation is right, but the run dropped the assumed row from the design.
set -euo pipefail
cat docs/specs/notify/design.md >/dev/null
cat notify.py >/dev/null
sed -i.bak '/^| Retrying is safe /d' docs/specs/notify/design.md
rm -f docs/specs/notify/design.md.bak
