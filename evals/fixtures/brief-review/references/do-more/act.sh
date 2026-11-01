#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -I -B - <<'FIX'
from pathlib import Path
path=Path("chatsvc/delivery_store.py")
text=path.read_text().replace("event_id TEXT PRIMARY KEY", "tenant TEXT, event_id TEXT, PRIMARY KEY(tenant, event_id)")
text=text.replace("def contains(self, event_id):", "def contains(self, tenant, event_id):")
text=text.replace("WHERE event_id = ?", "WHERE tenant = ? AND event_id = ?")
text=text.replace("(event_id,)", "(tenant, event_id)")
text=text.replace("def record(self, event_id):", "def record(self, tenant, event_id):")
text=text.replace("VALUES (?)", "VALUES (?, ?)")
path.write_text(text)
path=Path("chatsvc/delivery.py")
text=path.read_text().replace("receipts.contains(event.event_id)", "receipts.contains(event.tenant, event.event_id)")
text=text.replace("receipts.record(event.event_id)", "receipts.record(event.tenant, event.event_id)")
path.write_text(text)
FIX

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
