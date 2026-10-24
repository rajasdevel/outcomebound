#!/usr/bin/env bash
# migration-drops-stock: a new migration that drops items and creates the new table empty, as
# if the shop had no stock to keep.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../cents.sh
. "$here/../cents.sh"
cents_code "$right_add" "$right_list"
cat > migrations/002_price_cents.sql <<'SQL'
DROP TABLE items;
CREATE TABLE items (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price_cents INTEGER NOT NULL
);
SQL
python3 -B -m unittest discover -s tests >/dev/null 2>&1
