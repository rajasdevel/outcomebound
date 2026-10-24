#!/usr/bin/env bash
# one-brief: as good, but the answer gives one brief for both decisions.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../engine.sh
. "$here/../engine.sh"
cat logs/uploads.csv >/dev/null
cat docs/storage.md >/dev/null
cat logs/endpoints.csv >/dev/null
mkdir -p .agents/work
engine explorable new .agents/work/disk.source.html --kind decision
cp "$here/../good/disk.source.html" .agents/work/disk.source.html
cp "$here/../good/briefs.json" .agents/work/briefs.json
engine explorable build .agents/work/disk.source.html
engine explorable check .agents/work/disk.html
