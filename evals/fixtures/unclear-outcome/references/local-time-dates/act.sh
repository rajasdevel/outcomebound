#!/usr/bin/env bash
# local-time-dates: `list` shows the due dates in the local time zone; the sixth is refused.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build.sh
. "$here/../build.sh"
cat AGENTS.md >/dev/null
cat reminders.py >/dev/null
build_reminders local refuse
