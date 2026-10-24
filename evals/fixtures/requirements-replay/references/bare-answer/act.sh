#!/usr/bin/env bash
# bare-answer: the good change, reported in one line that names no requirement, no correction
# and no source.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export yes cents kept
update_test
python3 -B -m unittest >/dev/null 2>&1
