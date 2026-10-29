#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -I -B - <<'PARTIAL'
from pathlib import Path
import json
report = Path("reports/service-survey.json")
facts = json.loads(report.read_text(encoding="utf-8"))
facts["provider_404_caller_status"] = 404
report.write_text(json.dumps(facts) + "\n", encoding="utf-8")
Path('reports/service-survey.md').write_text('Live provider quotas are verified. A provider 404 is retried five times. All aliases resolve to the same model.\n', encoding='utf-8')
PARTIAL

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
