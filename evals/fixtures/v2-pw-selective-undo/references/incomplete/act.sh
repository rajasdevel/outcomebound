#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# One of the two settings only.
python3 -B "$here/../drop-retry.py" RETRY_LIMIT
