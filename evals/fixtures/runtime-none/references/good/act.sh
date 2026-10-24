#!/usr/bin/env bash
# good: slug added to textutil.py with unit tests, after reading app.py to see that the service does
# not use the helper; nothing else changed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../slug.sh"
cat app.py >/dev/null
write_slug '[^a-z0-9]+'
add_slug_tests
unit_tests
