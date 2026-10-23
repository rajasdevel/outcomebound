#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add promptkit/fetch.py tests/test_fetch.py
git commit -qm "fetch: raise the last error when every attempt fails" \
  -m "fetch_with_retry returned None after its last failed attempt, so a caller could store None as a result. It now raises the last TransientError, and does not wait after the last attempt."
# shellcheck source=../texts.sh
. "$here/../texts.sh"
