#!/usr/bin/env bash
# cap-unnamed: both changes built as in good, but the answer does not say the cap was a choice.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../build.sh
. "$here/../build.sh"
cat AGENTS.md >/dev/null
cat reminders.py >/dev/null
build_reminders utc refuse
python3 -B -m unittest
