#!/usr/bin/env bash
# registry-left-out: one ticket for the new module and its test; its bounds stop short of the registry, so the suite fails when it lands.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/markdown-format.md >/dev/null
cat audit/module_registry.py >/dev/null
write_ticket markdown-format "The report prints a Markdown table" docs/specs/markdown-format.md#decisions "formats, tests" tests ""
