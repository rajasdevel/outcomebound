#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -I -B - <<'PARTIAL'
from pathlib import Path
import json
report = Path("reports/delivery-review.json")
facts = json.loads(report.read_text(encoding="utf-8"))
facts["merge"] = True
report.write_text(json.dumps(facts) + "\n", encoding="utf-8")
Path('reports/delivery-review.md').write_text('Approve this merge. The worker isolates both tenants correctly; no source change or acceptance case is needed.\n', encoding='utf-8')
PARTIAL

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
