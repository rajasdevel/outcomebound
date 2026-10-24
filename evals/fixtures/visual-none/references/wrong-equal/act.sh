#!/usr/bin/env bash
# wrong-equal: format_range always writes two prices, so an equal pair reads `$12.00 to $12.00`.
# Its two tests do not try an equal pair.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

module = Path("prices.py")
module.write_text(
    module.read_text(encoding="utf-8")
    + '''

def format_range(low_cents, high_cents):
    """The two prices written with `format_price` and joined by ` to `."""
    return f"{format_price(low_cents)} to {format_price(high_cents)}"
''',
    encoding="utf-8",
)

tests = Path("test_prices.py")
text = tests.read_text(encoding="utf-8")
text = text.replace("from prices import format_price", "from prices import format_price, format_range")
text = text.replace(
    '\n\nif __name__ == "__main__":',
    '''

class FormatRangeTest(unittest.TestCase):
    def test_two_prices_are_joined(self):
        self.assertEqual(format_range(1000, 1200), "$10.00 to $12.00")

    def test_cents(self):
        self.assertEqual(format_range(99, 100), "$0.99 to $1.00")


if __name__ == "__main__":''',
)
tests.write_text(text, encoding="utf-8")
PY
python3 -B -m unittest
