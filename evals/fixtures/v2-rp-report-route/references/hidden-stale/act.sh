#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The inputs drive totals that are not shown; the totals that are shown never change.
python3 -B "$here/../page.py" --hidden-stale
