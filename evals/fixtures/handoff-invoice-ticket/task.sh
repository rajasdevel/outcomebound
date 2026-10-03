#!/usr/bin/env bash
# Print the message for the hand-off of ticket #8 with the ticket alone: see ../handoff/task.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/../handoff/task.sh" invoice ticket "${1:?usage: task.sh <workdir>}"
