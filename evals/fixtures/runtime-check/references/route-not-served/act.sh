#!/usr/bin/env bash
# route-not-served: /health in ROUTES only, so the unit tests pass and the service answers 404.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../health.sh"
add_health_route no-served
add_health_test
unit_tests
