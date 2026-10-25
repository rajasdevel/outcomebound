#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../references/document.sh"
# The suite ran (its own log says so), but the command is piped, so its status is not shown.
make -s test > /dev/null 2>&1
git add docs/cli.md
git commit -qm "docs: the --dry-run option of report"
