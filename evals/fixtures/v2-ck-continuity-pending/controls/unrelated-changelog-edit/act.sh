#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../../seeds/relay/reference.sh"
relay_check_start 4
relay_status
relay_code
relay_doc
relay_commit_items
printf -- '- slugify returns untitled for an empty slug\n' >> CHANGELOG.md
git add CHANGELOG.md
git commit -qm 'changelog: the fallback'
relay_wait_passed
relay_record
