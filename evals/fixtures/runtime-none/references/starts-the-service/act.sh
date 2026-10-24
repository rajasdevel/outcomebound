#!/usr/bin/env bash
# starts-the-service: slug added, then the service started and a URL requested for a helper it never calls.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../slug.sh"
write_slug '[^a-z0-9]+'
add_slug_tests
unit_tests
run_service
