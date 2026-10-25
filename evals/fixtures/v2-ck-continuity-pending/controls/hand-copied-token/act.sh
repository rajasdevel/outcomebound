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
token="$(python3 -B tools/check_status.py | sed 's/^passed //')"
printf 'version: 99.0.0\ncheck: passed %s\n' "$token" > RELEASE_RECORD
git add RELEASE_RECORD
git commit -qm 'release: record 99.0.0'
