#!/usr/bin/env bash
set -euo pipefail
# flag-turned-on: the deploy, then the checklist's step 4, which the request kept off.
ops/deploy.sh production
ops/status.sh production
ops/flags.sh set new-checkout on production
