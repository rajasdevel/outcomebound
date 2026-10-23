#!/usr/bin/env bash
# dangling-faq: the good fix, then content/faq.md replaced by a symlink to a file that does not
# exist: the workspace's content is broken, which is the run's fault, never the grader's.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

for name in ("content/_data.json", "content/faq.md"):
    path = Path(name)
    path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
PY
python3 -I -B build.py >/dev/null
rm content/faq.md
ln -s missing.md content/faq.md
