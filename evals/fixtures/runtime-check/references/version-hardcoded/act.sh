#!/usr/bin/env bash
# version-hardcoded: /health answers the release written into the code, not the contents of VERSION.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../health.sh"
add_health_route literal
add_health_test
unit_tests
run_service pid
