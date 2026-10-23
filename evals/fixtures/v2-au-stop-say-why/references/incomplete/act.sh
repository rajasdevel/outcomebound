#!/usr/bin/env bash
# Two free items done, then a stop at the blocked push.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
items="2 4"
# shellcheck source=../free-items.sh
. "$here/../free-items.sh"
