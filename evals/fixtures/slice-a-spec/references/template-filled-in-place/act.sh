#!/usr/bin/env bash
# template-filled-in-place: the ticket template itself filled in with one ticket whose bounds
# name the four files of the design, and no draft file under docs/tickets. The template is not a
# draft.
set -euo pipefail
cat docs/specs/csv-report.md >/dev/null
python3 -I -B - <<'PY'
from pathlib import Path

path = Path(".github/ISSUE_TEMPLATE/ticket.md")
text = path.read_text(encoding="utf-8")
text = text.replace("## Outcome\n", "## Outcome\nThe report prints CSV on request.\n", 1)
text = text.replace("reads:", "reads: docs/specs/csv-report.md#decisions", 1)
text = text.replace("bounds:", "bounds: report.py, expenses.py, test_report.py, README.md", 1)
text = text.replace("done-when:", "done-when:\n- report-tests", 1)
path.write_text(text, encoding="utf-8")
PY
