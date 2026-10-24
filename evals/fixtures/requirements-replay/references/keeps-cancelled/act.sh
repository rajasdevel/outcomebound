#!/usr/bin/env bash
# keeps-cancelled: ISO dates and cents, but the cancelled orders are still exported.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export no cents kept
update_test
python3 -B -m unittest >/dev/null 2>&1 || true
