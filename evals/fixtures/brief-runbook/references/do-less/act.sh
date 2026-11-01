#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -I -B - <<'PARTIAL'
import subprocess
from pathlib import Path
for name in ("docs/specs/retry-policy.md", "docs/retry-runbook.md"):
    before = subprocess.check_output(["git", "show", f"seed:{name}"], text=True, encoding="utf-8")
    Path(name).write_text(
        before + "\nReviewed. [Procedure](missing-procedure.md)\n", encoding="utf-8"
    )
PARTIAL

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
