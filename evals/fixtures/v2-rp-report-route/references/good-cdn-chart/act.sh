#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# A chart from a CDN beside the working page; its totals need no library, so offline the report works.
python3 -B "$here/../page.py" --cdn
