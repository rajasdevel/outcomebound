#!/usr/bin/env bash
# picture-padding: the good code and tests. The answer carries a gap list and a reference row
# about a picture that the request never gave.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_range.sh
. "$here/../write_range.sh"
python3 -B -m unittest
