#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The totals are redrawn only when a form is submitted with a Calculate button, id calculate.
python3 -B "$here/../page.py" --calculate
