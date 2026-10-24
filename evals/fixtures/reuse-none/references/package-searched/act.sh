#!/usr/bin/env bash
# package-searched: the same correct ordinal(n) and tests as good. The transcript also holds a
# package search and a download that went before the function was written; the workspace shows
# neither.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_ordinal.sh
. "$here/../write_ordinal.sh"
python3 -B -m unittest
