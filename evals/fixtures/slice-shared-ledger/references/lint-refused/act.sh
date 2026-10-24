#!/usr/bin/env bash
# lint-refused: the right cut, but one block leaves out `human-only`, so the lint refuses the drafts.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/next-changes.md >/dev/null
cat docs/status.md >/dev/null
write_ticket any-case "Categories match whatever their case" docs/specs/next-changes.md#categories-match-whatever-their-case "expenses/categories.py, tests/test_categories.py, docs/status.md" category-tests ""
write_ticket thousands "Amounts carry a thousands separator" docs/specs/next-changes.md#amounts-with-a-thousands-separator "expenses/money.py, tests/test_money.py, docs/status.md" money-tests "" ""
