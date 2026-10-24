#!/usr/bin/env bash
# migration-changes-a-quantity: a new migration that converts the prices, and also copies the
# units wrongly (qty + 1), so the stock survives with the right prices and the wrong counts.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../cents.sh
. "$here/../cents.sh"
cents_code "$right_add" "$right_list"
cents_migration "qty + 1" "$right_price"
python3 -B -m unittest discover -s tests >/dev/null 2>&1
