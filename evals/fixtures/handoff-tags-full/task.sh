#!/usr/bin/env bash
# Print the message for the hand-off of ticket #9 with the ticket compiled with `--detail full`: see ../handoff/task.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$here/../handoff/task.sh" tags full "${1:?usage: task.sh <workdir>}"
