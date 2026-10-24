#!/usr/bin/env bash
set -euo pipefail
# no-read-claims-live: the deploy ran and its job passed; what production serves was never read.
ops/deploy.sh production
