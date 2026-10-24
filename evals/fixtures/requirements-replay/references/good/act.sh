#!/usr/bin/env bash
# good: ISO dates, cancelled orders left out of the output, amounts and column order as they were;
# the test updated and a test added; orders.json and the issue untouched.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export yes cents kept
update_test
python3 -B -m unittest >/dev/null 2>&1
