#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, with both inputs read-only.
python3 -B "$here/../page.py" --readonly
