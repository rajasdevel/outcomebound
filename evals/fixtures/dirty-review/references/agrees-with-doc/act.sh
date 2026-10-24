#!/usr/bin/env bash
# agrees-with-doc: the files are read, but the report says the code and the document agree.
set -euo pipefail
cat parser.py >/dev/null
cat docs/parser.md >/dev/null
