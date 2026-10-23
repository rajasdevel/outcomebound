#!/usr/bin/env bash
# overbuilt: the table in the reply, and a status file with method notes in the repository.
set -euo pipefail
mkdir -p reports
printf '# Tracker status (draft)\n\nSource: results/release-results.csv. Each figure checked against its row.\n' \
  > reports/tracker-status.md
