#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page; a recommendation shows while the requests are over 4 million and is gone at the expected traffic.
python3 -B "$here/../page.py" --conditional
