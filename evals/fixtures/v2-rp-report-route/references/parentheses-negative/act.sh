#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Every total is worked out and shown as a negative amount in parentheses.
python3 -B "$here/../page.py" --parentheses
