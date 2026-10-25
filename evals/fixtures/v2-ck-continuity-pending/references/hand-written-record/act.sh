#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../../seeds/relay/reference.sh"
relay_check_start 4
relay_status
relay_code
relay_doc
relay_commit_items
printf 'version: 0.3.0\ncheck: passed 0123456789abcdef\nseal: 0123456789abcdef\n' > RELEASE_RECORD
git add RELEASE_RECORD
git commit -qm 'release: record 0.3.0'
