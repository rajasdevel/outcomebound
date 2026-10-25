#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The totals are redrawn only when a "Calculate" button is clicked; the button has no id, so the check does not know to click it.
python3 -B "$here/../page.py" --calculate-noid
