#!/usr/bin/env bash
# no-contradiction: the parser is read and reviewed, but not against its document.
set -euo pipefail
cat parser.py >/dev/null
git status --short >/dev/null
git diff >/dev/null
