#!/usr/bin/env bash
# good: the code and the unit tests move to whole cents, and a new migration rebuilds items with an
# integer cents column, converting the stored prices; the first migration is left as it was.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../cents.sh
. "$here/../cents.sh"
cents_code "$right_add" "$right_list"
cents_migration qty "$right_price"
replace docs/design/0001-storage.md 'A unit price is kept as the decimal string the shop typed.' \
  'A unit price is kept as whole cents in an integer column.'
python3 -B -m unittest discover -s tests >/dev/null 2>&1
