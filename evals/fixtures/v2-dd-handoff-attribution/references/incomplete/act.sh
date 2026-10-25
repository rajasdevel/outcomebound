#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
# Off by one: an order placed exactly 30 days before is refused too.
shop_rule billing ">="
python3 -B -m unittest discover -s tests -t . 2>/dev/null
