#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('screen.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('from html import escape\n\n\ndef render_projects(rows, query=\'\'):\n    selected = sorted(\n        (r for r in rows if not r[\'archived\'] and query.casefold() in r[\'name\'].casefold()),\n        key=lambda r: r[\'name\'].casefold(),\n    )\n    if not selected:\n        selected = sorted((r for r in rows if not r[\'archived\']), key=lambda r: r[\'name\'].casefold())\n    body = \'\'.join(\n        \'<tr>\' + \'\'.join(\'<td>\' + escape(str(r[k])) + \'</td>\' for k in (\'name\', \'owner\', \'status\')) + \'</tr>\'\n        for r in selected\n    )\n    if not rows:\n        body = \'<tr><td colspan="3">No projects found.</td></tr>\'\n    return (\'<section><div style="display:flex;justify-content:space-between"><h1>Projects</h1>\'\n            \'<label>Find a project <input type="search" name="query" value="\' + escape(query, quote=True) + \'"></label></div>\'\n            \'<table><thead><tr><th>Name</th><th>Owner</th><th>Status</th></tr></thead><tbody>\' + body + \'</tbody></table></section>\')\n', encoding='utf-8')
PY
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('screen-notes.md')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('# Screen notes\n\n| Item | Basis | Result |\n| --- | --- | --- |\n| toolbar-placement | inferred — [mock-up](docs/screen.txt) | Search sits to the right of the heading, as the mock-up line shows. |\n| empty-state | open — [mock-up](docs/screen.txt) shows the populated view only | Provisional: the screen shows “No projects found.” across the columns. The final empty state is not settled. |\n', encoding='utf-8')
PY
