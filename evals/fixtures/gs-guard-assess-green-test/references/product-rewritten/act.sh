#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('delivery.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("def queue_message(message, queue):\n    queue.append(message)\n    return 'queued'\n", encoding='utf-8')
PY
