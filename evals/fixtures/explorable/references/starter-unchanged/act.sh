#!/usr/bin/env bash
# starter-unchanged: a page is started and built, and its content stays the starter's.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../engine.sh
. "$here/../engine.sh"
cat logs/uploads.csv >/dev/null
cat docs/storage.md >/dev/null
cat logs/endpoints.csv >/dev/null
mkdir -p .agents/work
engine explorable new .agents/work/disk.source.html --kind decision
engine explorable build .agents/work/disk.source.html
engine explorable check .agents/work/disk.html
