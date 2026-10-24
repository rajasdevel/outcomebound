#!/usr/bin/env bash
# edits-first-migration: the column changed in migrations/001_items.sql itself. A new database is
# right and the unit tests pass; the shop's stock, which already has 001 applied, is not converted.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../cents.sh
. "$here/../cents.sh"
cents_code "$right_add" "$right_list"
replace migrations/001_items.sql 'price TEXT NOT NULL' 'price_cents INTEGER NOT NULL'
python3 -B -m unittest discover -s tests >/dev/null 2>&1
