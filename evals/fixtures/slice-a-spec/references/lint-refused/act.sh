#!/usr/bin/env bash
# lint-refused: one ticket with real bounds, but its block leaves out the `human-only` field, so
# the engine's draft lint refuses it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/csv-report.md >/dev/null
write_ticket csv-report "The report prints CSV on request" docs/specs/csv-report.md#decisions "report.py, expenses.py, test_report.py, README.md" report-tests "" ""
