#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The cost leaves out the included requests and storage.
python3 -B "$here/../page.py" --wrong
