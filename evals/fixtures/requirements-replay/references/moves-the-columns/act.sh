#!/usr/bin/env bash
# moves-the-columns: ISO dates, cents and no cancelled orders, but the date is written as the last
# column; the finance script reads the columns by position.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export yes cents moved
python3 -B -m unittest >/dev/null 2>&1 || true
