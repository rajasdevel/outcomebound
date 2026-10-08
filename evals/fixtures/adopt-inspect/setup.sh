#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -B "$here/../adoption/case.py" setup "${1:?usage: setup.sh <dir>}" inspect
