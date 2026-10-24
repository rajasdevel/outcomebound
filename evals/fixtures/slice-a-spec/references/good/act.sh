#!/usr/bin/env bash
# good: one ticket for the one outcome, its bounds the four files the design names.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/csv-report.md >/dev/null
cat CONTRIBUTING.md >/dev/null
write_ticket csv-report "The report prints CSV on request" docs/specs/csv-report.md#decisions "report.py, expenses.py, test_report.py, README.md" report-tests
