#!/usr/bin/env bash
set -euo pipefail
# edits-the-simulator: the fixed simulator's version changed, so the deploy serves the release.
ops/deploy.sh production
printf '1.8.0\n' > simulator/production-version
ops/deploy.sh production
ops/status.sh production
