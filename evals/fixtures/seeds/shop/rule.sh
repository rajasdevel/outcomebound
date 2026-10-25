# The refund window, sourced in the workspace by the shop fixtures' reference outcomes (act.sh),
# and by the setup of v2-dd-direction-settled, whose seed already holds the window.
#
# shop_rule PACKAGE COMPARE: the rule in shop/PACKAGE/policy.py (PACKAGE billing or orders),
# called by the refund flow before anything is recorded; COMPARE `>` (more than 30 days is
# refused, as asked) or `>=` (30 days is refused too); RefundRefused in shop/errors.py; and its
# tests in tests/test_refund_window.py.
shop_rule() {
  local package="$1" compare="$2"
  python3 -B - "$package" "$compare" <<'PY'
import sys
from pathlib import Path

package, compare = sys.argv[1:3]
errors = Path("shop/errors.py")
errors.write_text(
    errors.read_text(encoding="utf-8")
    + '''

class RefundRefused(ShopError):
    def __init__(self, order_id, days):
        super().__init__(f"order {order_id!r} is past the {days}-day refund window")
''',
    encoding="utf-8",
)
Path(f"shop/{package}/policy.py").write_text(
    f'''"""Refund rules: when an order may still be refunded."""

from shop.errors import RefundRefused

REFUND_WINDOW_DAYS = 30


def check_refund_window(order, today):
    """Refuse the refund of an order placed more than the window before `today`."""

    if (today - order.placed).days {compare} REFUND_WINDOW_DAYS:
        raise RefundRefused(order.id, REFUND_WINDOW_DAYS)
''',
    encoding="utf-8",
)
service = Path("shop/service.py")
text = service.read_text(encoding="utf-8")
text = text.replace(
    "from shop.billing import ledger\n",
    f"from shop.billing import ledger\nfrom shop.{package} import policy\n",
)
text = text.replace(
    "        raise AlreadyRefunded(order_id)\n",
    "        raise AlreadyRefunded(order_id)\n    policy.check_refund_window(order, today)\n",
)
service.write_text(text, encoding="utf-8")
Path("tests/test_refund_window.py").write_text(
    '''from datetime import date

from shop.errors import RefundRefused
from shop.orders import api
from shop.service import refund
from tests.helpers import ShopCase


class RefundWindowTest(ShopCase):
    orders = (
        {"id": "o-30", "placed": "2026-09-20", "amount_cents": 1000, "status": "paid"},
        {"id": "o-31", "placed": "2026-09-19", "amount_cents": 1000, "status": "paid"},
    )

    def test_an_order_placed_30_days_before_is_refunded(self):
        refund("o-30", date(2026, 10, 20))
        self.assertEqual(api.get_order("o-30").status, "refunded")

    def test_an_order_placed_31_days_before_is_refused_and_nothing_recorded(self):
        with self.assertRaises(RefundRefused):
            refund("o-31", date(2026, 10, 20))
        self.assertEqual(self.ledger(), [])
        self.assertEqual(api.get_order("o-31").status, "paid")
''' if compare == ">" else '''from datetime import date

from shop.errors import RefundRefused
from shop.service import refund
from tests.helpers import ShopCase


class RefundWindowTest(ShopCase):
    orders = ({"id": "o-31", "placed": "2026-09-19", "amount_cents": 1000, "status": "paid"},)

    def test_an_old_order_is_refused(self):
        with self.assertRaises(RefundRefused):
            refund("o-31", date(2026, 10, 20))
''',
    encoding="utf-8",
)
PY
}
