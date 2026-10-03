#!/usr/bin/env bash
# Build the hand-off of ticket #7 with the ticket and the design package: see ../handoff/build.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/../handoff/build.sh" duration design "${1:?usage: setup.sh <dir>}"
