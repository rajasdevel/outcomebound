#!/usr/bin/env bash
# drop-oldest: `list` shows the UTC dates, and a sixth reminder drops the oldest of the five.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build.sh
. "$here/../build.sh"
cat AGENTS.md >/dev/null
cat reminders.py >/dev/null
build_reminders utc drop
python3 -B -m unittest
