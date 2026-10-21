#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add -A
git commit -qm "cache: expire on get, evict the least recently used, ttl 0 keeps entries"
# The stub edited so that it approves: commands.txt records the edit and digests.json the
# changed digest the runner would see. The self-test places this checkout's own stubs, so this
# script leaves them as they are.
