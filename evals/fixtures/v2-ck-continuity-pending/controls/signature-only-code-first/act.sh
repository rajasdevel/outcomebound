#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../../seeds/relay/reference.sh"
relay_check_start 4
relay_status
relay_code_signature_only
relay_commit_code
relay_wait_passed
relay_doc
relay_commit_doc
relay_record
