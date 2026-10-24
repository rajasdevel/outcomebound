#!/usr/bin/env bash
# wires-it-into-the-service: slug added, and the service changed to import it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../slug.sh"
write_slug '[^a-z0-9]+'
add_slug_tests
unit_tests
python3 -I -B - <<'PY'
from pathlib import Path

p = Path("app.py")
p.write_text(p.read_text(encoding="utf-8").replace("import os\n", "import os\n\nimport textutil\n", 1), encoding="utf-8")
PY
