#!/usr/bin/env bash
# Build the hand-off of ticket #8 with the ticket and the spec package, its fixed tests committed and failing: see ../handoff/build.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/../handoff/build.sh" invoice spec "${1:?usage: setup.sh <dir>}"
