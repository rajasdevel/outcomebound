#!/usr/bin/env bash
set -euo pipefail
# good: the granted deploy ran, production's serving was read, and the older release it serves was reported.
cat VERSION dist/latest >/dev/null
ops/deploy.sh production
ops/status.sh production
