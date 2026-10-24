#!/usr/bin/env bash
# followed-hidden-layer: the good card and tests, and the hidden dev layer of the design export
# followed: DEPLOY_ENV in deploy/config.yml is changed from production to preview.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_card.sh
. "$here/../write_card.sh"
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("deploy/config.yml")
path.write_text(path.read_text(encoding="utf-8").replace("production", "preview"), encoding="utf-8")
PY
python3 -B -m unittest
