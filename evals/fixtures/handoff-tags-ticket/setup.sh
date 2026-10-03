#!/usr/bin/env bash
# Build the hand-off of ticket #9 with the ticket alone: see ../handoff/build.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/../handoff/build.sh" tags ticket "${1:?usage: setup.sh <dir>}"
