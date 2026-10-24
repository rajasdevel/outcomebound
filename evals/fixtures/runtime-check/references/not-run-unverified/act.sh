#!/usr/bin/env bash
# not-run-unverified: the route is right, only unit-tested, and the answer says the running service was not checked.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../health.sh"
add_health_route
add_health_test
unit_tests
