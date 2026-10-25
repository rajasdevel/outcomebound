#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../document.sh"
make -s unit > /dev/null 2>&1
git add docs/cli.md
git commit -qm "docs: the --dry-run option of report"
