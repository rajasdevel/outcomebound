#!/usr/bin/env bash
# The message one hand-off fixture's implementer reads: `task.sh <base> <variant> <workdir>`.
#
# Run by evals/run.py after the workspace is built and its seed is final, so the brief is the
# engine's own rendering of this workspace at its seed commit: `outcomebound tickets brief`,
# this checkout's launcher, reading the base's accepted ticket from a tracker export made
# beside the fixture (export.py), never from the workspace. The variant decides what follows
# the brief:
#
#   ticket   the brief alone
#   design   the brief, then the design package <base>/design.md
#   spec     the brief, then the spec package <base>/spec.md, whose tests and stubs build.sh
#            committed in the seed
#   full     the brief rendered with `--detail full`
#
# then the hand-over every variant shares (handover.md). Nothing in the message names a tier or
# a model, so one package text reaches every implementer it is run on.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
base="${1:?usage: task.sh <base> <variant> <workdir>}"
variant="${2:?usage: task.sh <base> <variant> <workdir>}"
workdir="${3:?usage: task.sh <base> <variant> <workdir>}"
number="$(python3 -B "$here/export.py" --number "$base")"
export_file="$(mktemp)"
trap 'rm -f "$export_file"' EXIT
python3 -B "$here/export.py" "$base" > "$export_file"

detail=plain
lead="Build ticket #$number, which the maintainer has accepted. Its brief, compiled by \`outcomebound tickets brief\`, follows."
case "$variant" in
  ticket) ;;
  full) detail=full ;;
  design | spec)
    lead="Build ticket #$number, which the maintainer has accepted. Its brief, compiled by \`outcomebound tickets brief\`, follows, then the package written for this hand-off."
    ;;
  *) echo "task.sh: no variant $variant" >&2; exit 2 ;;
esac
brief="$(cd "$workdir" && "$repo/scripts/outcomebound" tickets brief . "#$number" \
  --input "$export_file" --detail "$detail")"

printf '%s\n\n%s\n\n' "$lead" "$brief"
case "$variant" in
  design | spec) printf '%s\n\n' "$(cat "$here/$base/$variant.md")" ;;
esac
cat "$here/handover.md"
