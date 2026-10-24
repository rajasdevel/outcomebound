#!/usr/bin/env bash
# gate-before-repair: the order reversed, the repair ticket waits on the gate, so the gate lands over findings.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/doc-gate.md >/dev/null
python3 tools/doclint.py src || true
write_ticket doc-gate "make check runs the docstring check" docs/specs/doc-gate.md#decisions "Makefile, .github/workflows/ci.yml" check ""
write_ticket doc-findings "src has no docstring finding" docs/specs/doc-gate.md#decisions "src/ledger" tests "doc-gate"
