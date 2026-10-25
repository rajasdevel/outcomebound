#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
# The attributed decision followed into shop/orders/.
shop_rule orders ">"
python3 -B -m unittest discover -s tests -t . 2>/dev/null
