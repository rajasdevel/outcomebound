#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, which sends the reader on to another address when it loads.
python3 -B "$here/../page.py" --navigate "http://example.invalid/hosting"
