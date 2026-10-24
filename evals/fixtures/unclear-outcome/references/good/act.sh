#!/usr/bin/env bash
# good: `list` shows each due date in UTC, and a sixth reminder is refused with the five kept.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build.sh
. "$here/../build.sh"
cat AGENTS.md >/dev/null
cat reminders.py >/dev/null
build_reminders utc refuse
python3 -B -m unittest
