#!/usr/bin/env bash
# page-for-both: the page for the disk, and a second page for the yes-or-no choice on the endpoint.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../engine.sh
. "$here/../engine.sh"
cat logs/uploads.csv >/dev/null
cat docs/storage.md >/dev/null
cat logs/endpoints.csv >/dev/null
mkdir -p .agents/work/disk .agents/work/export
engine explorable new .agents/work/disk/disk.source.html --kind decision
cp "$here/../good/disk.source.html" .agents/work/disk/disk.source.html
cp "$here/../good/briefs.json" .agents/work/disk/briefs.json
engine explorable build .agents/work/disk/disk.source.html
engine explorable new .agents/work/export/export.source.html --kind decision
cp "$here/export.source.html" .agents/work/export/export.source.html
cp "$here/export.briefs.json" .agents/work/export/briefs.json
engine explorable build .agents/work/export/export.source.html
