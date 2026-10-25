#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../../seeds/relay/reference.sh"
relay_run_tests() { :; }
relay_check_start 4
relay_status
relay_code
relay_add_hanging_test
relay_doc
relay_commit_items
relay_wait_passed
relay_record
