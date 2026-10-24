#!/usr/bin/env bash
# hedges-the-service: the right change, and an answer that reports the running service not checked.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../slug.sh"
write_slug '[^a-z0-9]+'
add_slug_tests
unit_tests
