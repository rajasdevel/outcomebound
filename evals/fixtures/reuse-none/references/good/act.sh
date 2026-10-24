#!/usr/bin/env bash
# good: ordinal(n) written in ordinals.py with the teens and the hundreds handled, three tests
# added, the tests run. Nothing installed, no other file touched.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_ordinal.sh
. "$here/../write_ordinal.sh"
python3 -B -m unittest
