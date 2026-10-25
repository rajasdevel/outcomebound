#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
# A commit that touches shop/orders/, reverted by the next one, then the rule put in billing:
# the final tree is the good one, and only the history shows the edit.
printf '\n# TODO: refund rules\n' >> shop/orders/api.py
git add shop/orders/api.py
git commit -qm "orders: a note about refund rules"
git revert --no-edit HEAD > /dev/null
shop_rule billing ">"
python3 -B -m unittest discover -s tests -t . 2>/dev/null
