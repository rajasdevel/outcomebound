#!/usr/bin/env bash
# template-filled-in-place: the ticket template itself filled in with right bounds, and no draft file under docs/tickets. The template is not a draft.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../slicing/ticket.sh
. "$here/../../../slicing/ticket.sh"
cat docs/specs/markdown-format.md >/dev/null
cat audit/module_registry.py >/dev/null
python3 -I -B - <<'PY'
from pathlib import Path

path = Path(".github/ISSUE_TEMPLATE/ticket.md")
text = path.read_text(encoding="utf-8")
text = text.replace("## Outcome\n", "## Outcome\nThe report prints a Markdown table.\n", 1)
text = text.replace("reads:", "reads: docs/specs/markdown-format.md#decisions", 1)
text = text.replace("bounds:", "bounds: formats/markdown_out.py, tests/test_markdown_out.py, audit/module_registry.py", 1)
text = text.replace("done-when:", "done-when:\n- tests", 1)
path.write_text(text, encoding="utf-8")
PY
