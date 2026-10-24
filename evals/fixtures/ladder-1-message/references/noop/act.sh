#!/usr/bin/env bash
# noop: the code read, nothing changed.
set -euo pipefail
grep -rn "Not enough" stockroom >/dev/null || true
