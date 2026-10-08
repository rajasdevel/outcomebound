#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -B "$here/../clause/setup.py" learning "${1:?usage: setup.sh <dir>}"
