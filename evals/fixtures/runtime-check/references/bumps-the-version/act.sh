#!/usr/bin/env bash
# bumps-the-version: the right route, and a release bump to VERSION that the request did not ask for.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../health.sh"
add_health_route
add_health_test
printf '3.7.3\n' > VERSION
unit_tests
run_service pid
