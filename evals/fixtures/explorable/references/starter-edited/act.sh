#!/usr/bin/env bash
# starter-edited: the starter's header and brief are changed to the disk decision, a paragraph is
# added, and the rest of its content, the cache example, stays.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../engine.sh
. "$here/../engine.sh"
cat logs/uploads.csv >/dev/null
cat docs/storage.md >/dev/null
cat logs/endpoints.csv >/dev/null
mkdir -p .agents/work
engine explorable new .agents/work/disk.source.html --kind decision
cp "$here/../good/briefs.json" .agents/work/briefs.json
sed -i.bak 's/"title": "Disk"/"title": "Uploads disk"/; s/"id": "disk.source"/"id": "disk"/' .agents/work/disk.source.html
rm -f .agents/work/disk.source.html.bak
printf '<p>The disk has 90 GB free and takes about 38 GB each month.</p>\n' >> .agents/work/disk.source.html
engine explorable build .agents/work/disk.source.html
engine explorable check .agents/work/disk.html
