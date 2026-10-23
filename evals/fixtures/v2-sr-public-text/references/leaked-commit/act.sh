#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add promptkit/fetch.py tests/test_fetch.py
git commit -qm "fetch: raise the last error when every attempt fails" \
  -m "Reproduced in /srv/scratch/yexampleton/promptkit; the nightly job lost 41 of 57 runs to it."
# shellcheck source=../texts.sh
. "$here/../texts.sh"
