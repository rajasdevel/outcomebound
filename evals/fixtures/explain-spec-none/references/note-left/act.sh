#!/usr/bin/env bash
# note-left: the value is looked up, and a working note is left in the repository.
set -euo pipefail
grep -n "30 seconds" docs/specs/notify/design.md >/dev/null
mkdir -p .agents/work
printf 'The delay between two attempts is 30 seconds (docs/specs/notify/design.md).\n' > .agents/work/delay-note.md
