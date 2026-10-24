#!/usr/bin/env bash
# registry-in-a-later-ticket: the registry entry cut into a second ticket after the module; the module ticket lands over a failing registry test.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/markdown-format.md >/dev/null
cat audit/module_registry.py >/dev/null
write_ticket markdown-module "The report prints a Markdown table" docs/specs/markdown-format.md#decisions "formats/markdown_out.py, tests/test_markdown_out.py" tests ""
write_ticket markdown-registry "The registry names the Markdown module" docs/specs/markdown-format.md#decisions "audit/module_registry.py" tests "markdown-module"
