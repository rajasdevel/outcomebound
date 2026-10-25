#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
# The window kept inside `shop.billing.ledger.issue_refund`, before the money is recorded, and not
# in a policy module the refund flow calls; its tests go through `shop.service.refund`.
shop_rule billing ">"
python3 -B - <<'PY'
from pathlib import Path

service = Path("shop/service.py")
text = service.read_text(encoding="utf-8")
text = text.replace("from shop.billing import policy\n", "")
text = text.replace("    policy.check_refund_window(order, today)\n", "")
service.write_text(text, encoding="utf-8")
Path("shop/billing/policy.py").unlink()
ledger = Path("shop/billing/ledger.py")
text = ledger.read_text(encoding="utf-8")
text = text.replace(
    "from shop.orders.store import data_dir\n",
    "from shop.errors import RefundRefused\nfrom shop.orders.store import data_dir\n\n"
    "REFUND_WINDOW_DAYS = 30\n",
)
text = text.replace(
    '    """Record the refund of `order` on `today`."""\n\n',
    '    """Record the refund of `order` on `today`, if it is inside the refund window."""\n\n'
    "    if (today - order.placed).days > REFUND_WINDOW_DAYS:\n"
    "        raise RefundRefused(order.id, REFUND_WINDOW_DAYS)\n\n",
)
ledger.write_text(text, encoding="utf-8")
PY
python3 -B -m unittest discover -s tests -t . 2>/dev/null
