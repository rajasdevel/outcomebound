#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Totals for the expected traffic only: no inputs and no ids.
python3 -B "$here/../page.py" --static
