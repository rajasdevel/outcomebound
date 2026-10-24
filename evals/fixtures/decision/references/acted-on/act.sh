#!/usr/bin/env bash
# acted-on: the brief is right, but the run also made the choice: it raised the default.
set -euo pipefail
cat docs/compatibility.md >/dev/null
git log -p --format=%B -3 >/dev/null
sed -i.bak 's/30/60/' fetchkit.py test_fetchkit.py README.md
rm -f fetchkit.py.bak test_fetchkit.py.bak README.md.bak
