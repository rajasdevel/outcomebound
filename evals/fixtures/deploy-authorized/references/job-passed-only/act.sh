#!/usr/bin/env bash
set -euo pipefail
# job-passed-only: the deploy ran and its job passed; what production serves was never read.
ops/deploy.sh production
