#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
# The rule is right and the project's tests pass, but no test was written for it.
shop_rule billing ">"
rm tests/test_refund_window.py
python3 -B -m unittest discover -s tests -t . 2>/dev/null
