#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Built with the engine's explain page and a chart of the costs: a source written here, joined to
# the shell by `outcomebound explorable build`, and the built page saved as the report. The built
# page loads the chart library from the network and falls back to the chart's data table without it.
repo="$(cd "$here/../../../../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
python3 -B "$here/../page.py" --engine "$work" --chart
"$repo/scripts/outcomebound" explorable build "$work/hosting.source.html" >/dev/null
mkdir -p reports
cp "$work/hosting.html" reports/hosting.html
