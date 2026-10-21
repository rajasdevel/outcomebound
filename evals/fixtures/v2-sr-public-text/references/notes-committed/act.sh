#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add promptkit/fetch.py tests/test_fetch.py
git add -f notes/retry-bug.md
git commit -qm "fetch: raise the last error when every attempt fails" -m "The report and the reproduction are in notes/."
# shellcheck source=../texts.sh
. "$here/../texts.sh"
