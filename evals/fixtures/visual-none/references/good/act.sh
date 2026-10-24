#!/usr/bin/env bash
# good: format_range written in prices.py with the equal pair folded to one price, three tests
# added, the tests run. No other file, no source work.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_range.sh
. "$here/../write_range.sh"
python3 -B -m unittest
