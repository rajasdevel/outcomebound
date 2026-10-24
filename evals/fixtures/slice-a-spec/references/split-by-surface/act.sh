#!/usr/bin/env bash
# split-by-surface: the one outcome cut into a ticket for each file it lands in. Each ticket is
# well formed and holds real paths; the cut is the defect.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/csv-report.md >/dev/null
cat CONTRIBUTING.md >/dev/null
write_ticket csv-writer "The report module writes CSV" docs/specs/csv-report.md#decisions report.py report-tests
write_ticket format-option "The command parses --format" docs/specs/csv-report.md#decisions expenses.py report-tests
write_ticket csv-tests-and-readme "Tests and README cover --format" docs/specs/csv-report.md#decisions "test_report.py, README.md" report-tests
