#!/usr/bin/env bash
# The first two defects fixed; the run ends before the one the reviewer raises next.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
defects="expiry recency"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add -A
git commit -qm "cache: expire on get, evict the least recently used"
