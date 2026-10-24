#!/usr/bin/env bash
# good: `list --below N` keeps the items with fewer than N units; plain `list` as it was.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../option.sh
. "$here/../option.sh"
add_option "qty < ?" None
python3 -B -m unittest discover -s tests >/dev/null 2>&1
