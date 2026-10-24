#!/usr/bin/env bash
# gate-only: the design's own words cut into one ticket; its bounds stop at where the gate is wired, and the findings the check reports are left out.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/doc-gate.md >/dev/null
write_ticket doc-gate "make check runs the docstring check" docs/specs/doc-gate.md#decisions "Makefile, .github/workflows/ci.yml" check ""
