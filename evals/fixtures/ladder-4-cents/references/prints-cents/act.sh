#!/usr/bin/env bash
# prints-cents: the storage and the migration are right, but `list` prints the stored cents as
# they are (1250), not as 12.50.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../cents.sh
. "$here/../cents.sh"
cents_code "$right_add" "{price}"
cents_migration qty "$right_price"
python3 -B -m unittest discover -s tests >/dev/null 2>&1
