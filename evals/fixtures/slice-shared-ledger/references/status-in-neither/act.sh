#!/usr/bin/env bash
# status-in-neither: two tickets with their module and test; the status table, which each change must update, is in neither set of bounds.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/next-changes.md >/dev/null
cat docs/status.md >/dev/null
write_ticket any-case "Categories match whatever their case" docs/specs/next-changes.md#categories-match-whatever-their-case "expenses/categories.py, tests/test_categories.py" category-tests ""
write_ticket thousands "Amounts carry a thousands separator" docs/specs/next-changes.md#amounts-with-a-thousands-separator "expenses/money.py, tests/test_money.py" money-tests ""
