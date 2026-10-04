#!/usr/bin/env bash
# Build the hand-off of ticket #8 with the ticket compiled with `--detail full`: see ../handoff/build.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/../handoff/build.sh" invoice full "${1:?usage: setup.sh <dir>}"
