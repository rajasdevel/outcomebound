#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# One paragraph of prices, two inputs that change nothing, and no total ids.
python3 -B "$here/../page.py" --paragraph
