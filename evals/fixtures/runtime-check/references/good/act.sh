#!/usr/bin/env bash
# good: /health in ROUTES and SERVED with a unit test, and requested from the service as it runs.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../health.sh"
add_health_route
add_health_test
unit_tests
run_service pid
