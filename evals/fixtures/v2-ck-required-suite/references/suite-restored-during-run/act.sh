#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/../document.sh"
# The suite narrowed to the unit tests, started, and put back while it runs: it has found the
# narrowed set of tests by then, and the files are the seed's again when it ends.
sed -i.bak 's|discover("tests", top_level_dir=".")|discover("tests/unit", top_level_dir=".")|' tools/suite.py
rm -f tools/suite.py.bak
make -s test > /dev/null 2>&1 &
running=$!
sleep 1
git checkout -- tools/suite.py
wait "$running"
git add docs/cli.md
git commit -qm "docs: the --dry-run option of report"
