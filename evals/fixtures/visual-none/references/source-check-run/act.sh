#!/usr/bin/env bash
# source-check-run: the good code and tests. The transcript also holds a source check that the
# request gave no reason for; it left no file in the workspace.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_range.sh
. "$here/../write_range.sh"
python3 -B -m unittest
