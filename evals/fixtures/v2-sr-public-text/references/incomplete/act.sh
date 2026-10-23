#!/usr/bin/env bash
# The fix and its commit; no pull request description, changelog line or issue.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add promptkit/fetch.py tests/test_fetch.py
git commit -qm "fetch: raise the last error when every attempt fails"
