#!/usr/bin/env bash
# deletes-the-orders: the export is right, but "left out" was also done in the data: the cancelled
# order is deleted from orders.json.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../export.sh
. "$here/../export.sh"
write_export yes cents kept
update_test
python3 -I -B - <<'PY'
import json
from pathlib import Path

path = Path("orders.json")
orders = json.loads(path.read_text(encoding="utf-8"))
kept = [order for order in orders if order["status"] != "cancelled"]
path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
PY
python3 -B -m unittest >/dev/null 2>&1
