#!/usr/bin/env bash
# good: the comparison fixed so that taking exactly the stock is allowed; the unit tests run.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
fix "if qty > have:"
python3 -B -m unittest discover -s tests >/dev/null 2>&1
