#!/usr/bin/env bash
# template-filled-in-place: the ticket template itself filled in with a gate ticket whose bounds
# are wide enough, and no draft file under docs/tickets. The template is not a draft.
set -euo pipefail
cat docs/specs/doc-gate.md >/dev/null
python3 -I -B - <<'PY'
from pathlib import Path

path = Path(".github/ISSUE_TEMPLATE/ticket.md")
text = path.read_text(encoding="utf-8")
text = text.replace("## Outcome\n", "## Outcome\nmake check runs the docstring check, and src has no finding.\n", 1)
text = text.replace("reads:", "reads: docs/specs/doc-gate.md#decisions", 1)
text = text.replace("bounds:", "bounds: Makefile, .github/workflows/ci.yml, src", 1)
text = text.replace("done-when:", "done-when:\n- check", 1)
path.write_text(text, encoding="utf-8")
PY
