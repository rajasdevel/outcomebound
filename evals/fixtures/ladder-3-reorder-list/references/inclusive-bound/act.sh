#!/usr/bin/env bash
# inclusive-bound: `--below N` also lists the items with exactly N units (`qty <= ?`).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../option.sh
. "$here/../option.sh"
add_option "qty <= ?" None
python3 -B -m unittest discover -s tests >/dev/null 2>&1
