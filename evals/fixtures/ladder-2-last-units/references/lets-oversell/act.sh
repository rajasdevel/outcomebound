#!/usr/bin/env bash
# lets-oversell: the comparison loosened by one too many, so the last units can be taken and so
# can one unit more than the stock holds.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
fix "if qty > have + 1:"
python3 -B -m unittest discover -s tests >/dev/null 2>&1 || true
