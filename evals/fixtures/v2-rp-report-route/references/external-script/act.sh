#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page with its script in reports/calculator.js, named by a script element.
python3 -B "$here/../page.py" --external
