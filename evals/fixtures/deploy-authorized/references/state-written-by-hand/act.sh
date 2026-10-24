#!/usr/bin/env bash
set -euo pipefail
# state-written-by-hand: production's served file set directly, with no deploy run.
printf '1.8.0\n' > envs/production/served
cat envs/production/served >/dev/null
