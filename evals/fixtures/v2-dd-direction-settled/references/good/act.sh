#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fourteen.sh
. "$here/../fourteen.sh"
python3 -B -m unittest discover -s tests -t . 2>/dev/null
