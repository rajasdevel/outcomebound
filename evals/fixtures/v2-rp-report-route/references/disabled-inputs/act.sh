#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, with both inputs disabled.
python3 -B "$here/../page.py" --disabled
