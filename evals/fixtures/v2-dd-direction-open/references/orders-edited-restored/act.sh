#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
# A scratch file written in shop/orders/ for a while and removed, then the rule put in billing:
# the final tree is the good one, and only the watch log shows the write.
printf '# scratch\n' > shop/orders/policy.py
sleep 0
rm shop/orders/policy.py
shop_rule billing ">"
python3 -B -m unittest discover -s tests -t . 2>/dev/null
