#!/usr/bin/env bash
# merged-by-the-status-table: both outcomes in one ticket because both set a row of the status table; one implementer would hold the other idle.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/next-changes.md >/dev/null
cat docs/status.md >/dev/null
write_ticket next-changes "Categories match whatever their case, and amounts carry a thousands separator" docs/specs/next-changes.md#categories-match-whatever-their-case "expenses, tests, docs/status.md" category-tests ""
