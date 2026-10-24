#!/usr/bin/env bash
# repair-partial: the gate is ordered after a repair ticket that covers only one of the two files with findings.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/doc-gate.md >/dev/null
python3 tools/doclint.py src || true
write_ticket doc-findings "src has no docstring finding" docs/specs/doc-gate.md#decisions "src/ledger/entries.py" tests ""
write_ticket doc-gate "make check runs the docstring check" docs/specs/doc-gate.md#decisions "Makefile, .github/workflows/ci.yml" check "doc-findings"
