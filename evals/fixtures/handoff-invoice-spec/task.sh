#!/usr/bin/env bash
# Print the message for the hand-off of ticket #8 with the ticket and the spec package, its fixed tests committed and failing: see ../handoff/task.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/../handoff/task.sh" invoice spec "${1:?usage: task.sh <workdir>}"
