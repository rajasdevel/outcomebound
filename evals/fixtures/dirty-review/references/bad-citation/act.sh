#!/usr/bin/env bash
# bad-citation: the review reads what it must, and cites lines the files do not hold.
set -euo pipefail
cat parser.py >/dev/null
cat docs/parser.md >/dev/null
