#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
workdir="${1:?usage: task.sh <workdir>}"
export_file="$(mktemp)"
trap 'rm -f "$export_file"' EXIT
python3 -B "$here/../handoff/export.py" duration > "$export_file"
cat <<'TASK'
Prepare the handoff message for the accepted duration ticket below. The person directly assigns
its designated implementer to the outcome tier. Return the message only. Do not build the
feature, write files, run implementation tests, launch an implementer, commit, change the
accepted ticket, contact a tracker or publish. The plain compiled brief follows. Work starts
in this checkout on its current branch. The project tests and landing policy are in its
existing instructions.
TASK
cd "$workdir"
"$repo/scripts/outcomebound" tickets brief . '#7' --input "$export_file" --detail plain
