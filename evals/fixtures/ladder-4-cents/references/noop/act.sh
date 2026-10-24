#!/usr/bin/env bash
# noop: the code and the migrations read, nothing changed.
set -euo pipefail
cat migrations/001_items.sql >/dev/null
