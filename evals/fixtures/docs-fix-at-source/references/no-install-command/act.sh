#!/usr/bin/env bash
# no-install-command: the good fix, but the shared install snippet replaced by a sentence: the
# pages show 3.0.0 and no longer say how to install it.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

for name in ("content/_data.json", "content/faq.md"):
    path = Path(name)
    path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
printf 'The current release is 3.0.0.\n' > content/_snippets/install-command.md
python3 -I -B build.py >/dev/null
