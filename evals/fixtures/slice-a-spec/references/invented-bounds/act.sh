#!/usr/bin/env bash
# invented-bounds: one ticket for the one outcome, but its bounds name files the repository does
# not hold (a package layout the design does not use).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/csv-report.md >/dev/null
cat CONTRIBUTING.md >/dev/null
write_ticket csv-report "The report prints CSV on request" docs/specs/csv-report.md#decisions "src/expenses/csv_writer.py, src/expenses/cli.py, tests/test_csv.py" report-tests
