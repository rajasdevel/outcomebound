#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add promptkit/fetch.py tests/test_fetch.py
git commit -qm "fetch: raise the last error when every attempt fails"
# shellcheck source=../texts.sh
. "$here/../texts.sh"
cat >> pr/description.md <<'MD'

Reported by Example Freight; a first fix drafted by model-x9 was discarded.
MD
