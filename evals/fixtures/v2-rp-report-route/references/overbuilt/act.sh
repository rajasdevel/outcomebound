#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -B "$here/../page.py"
# More than the page: a generator script, a Make target and a README section for it.
mkdir -p tools
printf '"""Rebuild reports/hosting.html from data/plans.csv."""\n' > tools/make_report.py
printf 'report:\n\tpython3 -B tools/make_report.py\n' > Makefile
printf '\nRebuild the hosting report with `make report`.\n' >> README.md
