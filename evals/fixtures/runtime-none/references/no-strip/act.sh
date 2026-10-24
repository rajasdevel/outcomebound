#!/usr/bin/env bash
# no-strip: runs replaced by one dash, with the dash left at either end.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../slug.sh"
write_slug '[^a-z0-9]+' nostrip
add_slug_tests weak
unit_tests
