#!/usr/bin/env bash
# ends-by-port: the service checked as in good, then ended by port instead of by its own process id.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../health.sh"
add_health_route
add_health_test
unit_tests
run_service port
