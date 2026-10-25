#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../../seeds/relay/reference.sh"
relay_check_start 4
relay_status
relay_code
relay_run_tests
git add slugkit tests
git commit -qm 'slugify: an empty slug becomes untitled'
relay_wait_passed
relay_record
