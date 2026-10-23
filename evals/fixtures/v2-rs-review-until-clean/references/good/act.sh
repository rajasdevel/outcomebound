#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add -A
git commit -qm "cache: expire on get, evict the least recently used, ttl 0 keeps entries"
