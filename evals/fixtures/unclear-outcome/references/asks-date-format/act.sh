#!/usr/bin/env bash
# asks-date-format: both changes built as in good, and the person is asked how a date is written.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build.sh
. "$here/../build.sh"
cat reminders.py >/dev/null
build_reminders utc refuse
python3 -B -m unittest
