#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The index reset for the whole file, then the retry settings taken out by hand.
git restore --staged app/settings.py
python3 -B "$here/../drop-retry.py"
