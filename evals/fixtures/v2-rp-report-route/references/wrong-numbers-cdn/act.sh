#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The cost leaves out the included allowances, and the page also loads a chart library from a CDN; offline it must be judged as the same page without the chart.
python3 -B "$here/../page.py" --wrong --cdn
