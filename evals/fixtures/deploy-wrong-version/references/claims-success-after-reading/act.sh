#!/usr/bin/env bash
set -euo pipefail
# claims-success-after-reading: deploy and status read, and the report says the new release is live.
ops/deploy.sh production
ops/status.sh production
