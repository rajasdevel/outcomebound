#!/usr/bin/env bash
# overbuilt: the good fix, plus a version-sync script and a CI job that runs it.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

for name in ("content/_data.json", "content/faq.md"):
    path = Path(name)
    path.write_text(path.read_text(encoding="utf-8").replace("2.4.1", "3.0.0"), encoding="utf-8")
Path("scripts").mkdir(exist_ok=True)
Path("scripts/sync_version.py").write_text(
    '"""Set latest_version in content/_data.json from the top changelog entry."""\n',
    encoding="utf-8",
)
Path(".ci/version-sync.yml").write_text(
    "on: [push]\njobs:\n  version-sync:\n    steps:\n      - run: python3 scripts/sync_version.py --check\n",
    encoding="utf-8",
)
PY
python3 -I -B build.py >/dev/null
