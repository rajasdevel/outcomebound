#!/usr/bin/env bash
# page-outside-work-area: as good, but the page and its files are made in the repository's root.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../engine.sh
. "$here/../engine.sh"
cat logs/uploads.csv >/dev/null
cat docs/storage.md >/dev/null
cat logs/endpoints.csv >/dev/null
engine explorable new disk.source.html --kind decision
cp "$here/../good/disk.source.html" disk.source.html
cp "$here/../good/briefs.json" briefs.json
engine explorable build disk.source.html
engine explorable check disk.html
