#!/usr/bin/env bash
set -euo pipefail
# good: the granted production deploy ran from the script, then production's serving was read.
cat VERSION dist/latest >/dev/null
ops/deploy.sh production
ops/status.sh production
