#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, and a script adds a recommendation, a choice of plan and a reply
# button after it loads: only the rendered page shows them.
python3 -B "$here/../page.py" --decision
