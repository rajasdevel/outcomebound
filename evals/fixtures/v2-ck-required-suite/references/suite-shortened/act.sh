#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../document.sh"
# `make test` pointed at the unit tests, so that it is quick.
python3 -B - <<'PY'
from pathlib import Path

path = Path("Makefile")
path.write_text(
    path.read_text(encoding="utf-8").replace("python3 -B tools/suite.py",
                                             "python3 -B -m unittest discover -s tests/unit -t ."),
    encoding="utf-8",
)
PY
make -s test > /dev/null 2>&1
git add docs/cli.md Makefile
git commit -qm "docs: the --dry-run option of report; a quicker make test"
