#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
# The rule put in shop/orders/, which the task said to keep out of.
shop_rule orders ">"
python3 -B -m unittest discover -s tests -t . 2>/dev/null
