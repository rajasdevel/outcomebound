#!/usr/bin/env bash
# lint-refused: the right bounds, but the block leaves out `human-only`, so the lint refuses it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/markdown-format.md >/dev/null
cat audit/module_registry.py >/dev/null
write_ticket markdown-format "The report prints a Markdown table" docs/specs/markdown-format.md#decisions "formats/markdown_out.py, tests/test_markdown_out.py, audit/module_registry.py" tests "" ""
