#!/usr/bin/env bash
# lint-refused: a ticket whose bounds are right but whose block leaves out `human-only`, so the lint refuses it; the gate claim still reads the bounds.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/doc-gate.md >/dev/null
write_ticket doc-gate "make check runs the docstring check" docs/specs/doc-gate.md#decisions "Makefile, .github/workflows/ci.yml, src" check "" ""
