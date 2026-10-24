#!/usr/bin/env bash
# gate-not-ordered: the repair ticket drawn, and the gate ticket not blocked by it, so the gate can land first and fail.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/doc-gate.md >/dev/null
python3 tools/doclint.py src || true
write_ticket doc-findings "src has no docstring finding" docs/specs/doc-gate.md#decisions "src/ledger" tests ""
write_ticket doc-gate "make check runs the docstring check" docs/specs/doc-gate.md#decisions "Makefile, .github/workflows/ci.yml" check ""
