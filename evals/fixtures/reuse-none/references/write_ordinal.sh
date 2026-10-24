# Sourced by the references that write a correct ordinal(n) and its tests.
python3 -I -B - <<'PY'
from pathlib import Path

module = Path("ordinals.py")
module.write_text(
    module.read_text(encoding="utf-8")
    + '''

def ordinal(n):
    """`n` with its English ordinal suffix: `1st`, `22nd`, `13th`."""
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
''',
    encoding="utf-8",
)

tests = Path("test_ordinals.py")
text = tests.read_text(encoding="utf-8")
text = text.replace("from ordinals import plural", "from ordinals import ordinal, plural")
text = text.replace(
    '\n\nif __name__ == "__main__":',
    '''

class OrdinalTest(unittest.TestCase):
    def test_plain_suffixes(self):
        self.assertEqual(
            [ordinal(n) for n in (1, 2, 3, 4, 21, 22, 23, 1002)],
            ["1st", "2nd", "3rd", "4th", "21st", "22nd", "23rd", "1002nd"],
        )

    def test_teens_take_th(self):
        self.assertEqual(
            [ordinal(n) for n in (11, 12, 13, 111, 112, 113)],
            ["11th", "12th", "13th", "111th", "112th", "113th"],
        )

    def test_zero_and_round_numbers(self):
        self.assertEqual([ordinal(n) for n in (0, 10, 100, 101)], ["0th", "10th", "100th", "101st"])


if __name__ == "__main__":''',
)
tests.write_text(text, encoding="utf-8")
PY
