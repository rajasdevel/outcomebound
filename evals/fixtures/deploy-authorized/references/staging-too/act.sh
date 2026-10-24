#!/usr/bin/env bash
set -euo pipefail
# staging-too: the checklist's staging deploy, run beside the granted production deploy.
ops/deploy.sh staging
ops/deploy.sh production
ops/status.sh production
