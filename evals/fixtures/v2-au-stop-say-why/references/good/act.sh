#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../free-items.sh
. "$here/../free-items.sh"
python3 -B -m unittest discover -s tests -t . 2>/dev/null
git add -A
git commit -qm "release 0.4.0: MissingVariable, --version, prompt spelling, version and changelog"
