#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The ids of Starter and Team carry each other's total.
python3 -B "$here/../page.py" --swapped
