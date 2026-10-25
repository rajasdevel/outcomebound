#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../../references/document.sh"
# The suite, the add and the commit in one `&&` chain, as one command.
make -s test > /dev/null 2>&1 && git add docs/cli.md && git commit -qm "docs: the --dry-run option of report"
