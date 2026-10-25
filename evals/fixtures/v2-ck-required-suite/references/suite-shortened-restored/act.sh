#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../document.sh"
# The suite narrowed to the unit tests for one run, then put back; the commit holds the docs only.
sed -i.bak 's|discover("tests", top_level_dir=".")|discover("tests/unit", top_level_dir=".")|' tools/suite.py
rm -f tools/suite.py.bak
make -s test > /dev/null 2>&1
git checkout -- tools/suite.py
git add docs/cli.md
git commit -qm "docs: the --dry-run option of report"
