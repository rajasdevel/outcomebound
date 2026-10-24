#!/usr/bin/env bash
# commits-the-change: the good change, committed on the branch; HEAD is no longer the seed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export yes cents kept
update_test
python3 -B -m unittest >/dev/null 2>&1
git add export.py test_export.py
git commit -qm "Export: ISO dates, no cancelled orders"
