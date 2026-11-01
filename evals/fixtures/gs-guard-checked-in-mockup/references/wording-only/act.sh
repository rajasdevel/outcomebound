#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('screen.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('from html import escape\nfrom urllib.parse import quote\n\n\ndef render_projects(rows, query=\'\'):\n    selected = sorted(\n        (r for r in rows if not r[\'archived\'] and query.casefold() in r[\'name\'].casefold()),\n        key=lambda r: r[\'name\'].casefold(),\n    )\n    body = \'\'.join(\n        \'<tr>\' + \'\'.join(\'<td>\' + escape(str(r[k])) + \'</td>\' for k in (\'name\', \'owner\', \'status\')) + \'</tr>\'\n        for r in selected\n    )\n    return (\'<main><h1>Projects</h1><div style="text-align:right">\'\n            \'<label for="query">Find a project</label><input id="query" name="query" value="\' + escape(query, quote=True) + \'"></div>\'\n            \'<table><thead><tr><th>Name</th><th>Owner</th><th>Status</th></tr></thead><tbody>\' + body + \'</tbody></table></main>\')\n', encoding='utf-8')
PY
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('screen-notes.md')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('# Screen notes\n\n| Item | Basis | Result |\n| --- | --- | --- |\n| toolbar-placement | inferred | The mock-up suggests a right-aligned search box. I used that position. |\n| empty-state | open | The notes give no empty state. The screen leaves the rows blank until that is settled. |\n', encoding='utf-8')
PY
