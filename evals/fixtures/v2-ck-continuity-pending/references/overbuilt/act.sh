#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../../seeds/relay/reference.sh"
relay_check_start 4
relay_status
relay_code
relay_doc
relay_commit_items
relay_wait_passed
relay_record

printf '# slugkit\n' > README.md
git add README.md
git commit -qm 'add a README'
