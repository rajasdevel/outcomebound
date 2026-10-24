# Sourced by the references that write a correct format_range and its tests.
python3 -I -B - <<'PY'
from pathlib import Path

module = Path("prices.py")
module.write_text(
    module.read_text(encoding="utf-8")
    + '''

def format_range(low_cents, high_cents):
    """The two prices written with `format_price` and joined by ` to `.

    One price where the two are equal: `$12.00`, not `$12.00 to $12.00`.
    """
    if low_cents == high_cents:
        return format_price(low_cents)
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
        self.assertEqual(format_range(1999, 2500), "$19.99 to $25.00")

    def test_equal_prices_are_written_once(self):
        self.assertEqual(format_range(1200, 1200), "$12.00")
        self.assertEqual(format_range(5, 5), "$0.05")

    def test_zero_and_cents(self):
        self.assertEqual(format_range(0, 5), "$0.00 to $0.05")
        self.assertEqual(format_range(99, 100), "$0.99 to $1.00")


if __name__ == "__main__":''',
)
tests.write_text(text, encoding="utf-8")
PY
