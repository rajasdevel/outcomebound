#!/usr/bin/env bash
# default-limit: `--below` defaults to 10 so that `list` always filters; plain `list` no longer
# prints the items with 10 units or more.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../option.sh
. "$here/../option.sh"
add_option "qty < ?" 10
python3 -B -m unittest discover -s tests >/dev/null 2>&1
