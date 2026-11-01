#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -I -B - "$here/files" <<'COPY'
import shutil
import sys
from pathlib import Path
source = Path(sys.argv[1])
for path in sorted(source.rglob("*")):
    if path.is_file():
        target = Path(str(path.relative_to(source)).removesuffix(".in"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
COPY
python3 -I -B - <<'CHANGELOG'
from pathlib import Path
path = Path("CHANGELOG.md")
path.write_text(path.read_text().replace("## Unreleased", "## Unreleased\n\n- Docs: clarify retries, total attempts and rerun grants.", 1))
CHANGELOG
python3 -B tools/docs_check.py

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
