#!/usr/bin/env bash
# noop: the code read, nothing changed.
set -euo pipefail
grep -n "have" stockroom/store.py >/dev/null
