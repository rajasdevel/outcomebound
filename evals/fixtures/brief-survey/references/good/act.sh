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
python3 -B -m unittest tests.test_config tests.test_retry tests.test_limits

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
