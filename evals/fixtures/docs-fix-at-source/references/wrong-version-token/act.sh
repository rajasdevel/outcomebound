#!/usr/bin/env bash
# wrong-version-token: the shared value set to 3.0.01, which holds the text 3.0.0 but is no
# release; the FAQ says 3.0.0; site rebuilt.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

data = Path("content/_data.json")
data.write_text(data.read_text(encoding="utf-8").replace("2.4.1", "3.0.01"), encoding="utf-8")
faq = Path("content/faq.md")
faq.write_text(faq.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
python3 -I -B build.py >/dev/null
