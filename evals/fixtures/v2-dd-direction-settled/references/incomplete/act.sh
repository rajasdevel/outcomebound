#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The constant only: the tests still expect 30 days to be refunded.
tests=keep
# shellcheck source=../fourteen.sh
. "$here/../fourteen.sh"
