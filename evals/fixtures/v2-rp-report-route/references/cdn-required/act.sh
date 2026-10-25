#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The cost is worked out with a library loaded from a CDN: with the network denied, the totals are empty.
python3 -B "$here/../page.py" --cdn-required
