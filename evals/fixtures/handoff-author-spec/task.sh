#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
workdir="${1:?usage: task.sh <workdir>}"
export_file="$(mktemp)"
trap 'rm -f "$export_file"' EXIT
python3 -B "$here/../handoff/export.py" duration > "$export_file"
cat <<'TASK'
Prepare the first handoff package for the accepted duration ticket below. The person directly
assigns its designated implementer to the spec tier. Return the handoff message; do not launch
an implementer or build the feature. Read the current code. You may add test files under
`tests/` and run them with local Python and unittest. Keep existing files unchanged. Do not
commit, edit the accepted ticket, contact a tracker or publish. Prepare this step only. No
earlier step exists; do not invent a review. The full compiled brief follows.
TASK
cd "$workdir"
"$repo/scripts/outcomebound" tickets brief . '#7' --input "$export_file" --detail full
