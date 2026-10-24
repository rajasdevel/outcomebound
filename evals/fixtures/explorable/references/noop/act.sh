#!/usr/bin/env bash
# noop: the data is read; nothing is built.
set -euo pipefail
cat logs/uploads.csv >/dev/null
cat docs/storage.md >/dev/null
cat logs/endpoints.csv >/dev/null
