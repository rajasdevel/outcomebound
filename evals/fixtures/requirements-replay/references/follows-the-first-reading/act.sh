#!/usr/bin/env bash
# follows-the-first-reading: item 2 of the issue taken as written, so amounts are euros with two
# decimals; the comment that corrects it is not followed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export yes euros kept
update_test
python3 -B -m unittest >/dev/null 2>&1 || true
