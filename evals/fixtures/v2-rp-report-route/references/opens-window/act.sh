#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, which opens a window when it loads.
python3 -B "$here/../page.py" --open http://example.invalid/hosting
