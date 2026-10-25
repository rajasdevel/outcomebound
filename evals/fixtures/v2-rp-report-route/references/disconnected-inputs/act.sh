#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Totals typed in for the expected traffic, with their ids; the two inputs change nothing.
python3 -B "$here/../page.py" --disconnected
