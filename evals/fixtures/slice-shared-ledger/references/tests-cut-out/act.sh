#!/usr/bin/env bash
# tests-cut-out: each change cut into a code ticket and a test ticket; the outcomes stay apart and share the status table, and there are four tickets, not two.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/next-changes.md >/dev/null
cat docs/status.md >/dev/null
write_ticket any-case "Categories match whatever their case" docs/specs/next-changes.md#categories-match-whatever-their-case "expenses/categories.py, docs/status.md" category-tests ""
write_ticket any-case-tests "Categories match whatever their case: tests" docs/specs/next-changes.md#categories-match-whatever-their-case "tests/test_categories.py" category-tests "any-case"
write_ticket thousands "Amounts carry a thousands separator" docs/specs/next-changes.md#amounts-with-a-thousands-separator "expenses/money.py, docs/status.md" money-tests ""
write_ticket thousands-tests "Amounts carry a thousands separator: tests" docs/specs/next-changes.md#amounts-with-a-thousands-separator "tests/test_money.py" money-tests "thousands"
