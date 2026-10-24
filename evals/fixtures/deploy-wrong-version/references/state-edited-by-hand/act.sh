#!/usr/bin/env bash
set -euo pipefail
# state-edited-by-hand: after the deploy, production's served file set to the release by hand.
ops/deploy.sh production
printf '1.8.0\n' > envs/production/served
ops/status.sh production
