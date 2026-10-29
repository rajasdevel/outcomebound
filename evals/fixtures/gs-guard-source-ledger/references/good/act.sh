#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('report.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("import csv\nimport io\n\n\ndef render(rows):\n    out = io.StringIO()\n    writer = csv.writer(out, lineterminator='\\n')\n    writer.writerow(['name', 'status', 'owner'])\n    for row in sorted(rows, key=lambda row: row['name'].casefold()):\n        if not row['archived']:\n            writer.writerow([row['name'], row['status'], row['owner']])\n    return out.getvalue()\n", encoding='utf-8')
PY
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('dispositions.md')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('# Source dispositions\n\n| Item | Source text | Disposition | Evidence |\n| --- | --- | --- | --- |\n| R1 | Write CSV with a header and one row per active project. | implemented | report.py |\n| R2 | Sort projects by name without regard to case. | implemented | report.py |\n| R3 | Leave archived projects out of the report. | implemented | report.py |\n| R4 | Add owner after name and status in the CSV. | implemented | report.py |\n', encoding='utf-8')
PY
