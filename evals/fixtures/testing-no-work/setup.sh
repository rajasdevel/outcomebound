#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -B "$here/setup_testing_no_work.py" "${1:?usage: setup.sh <dir>}"
