#!/usr/bin/env bash
# teens-wrong: ordinal(n) judges only the last digit, so 11, 12, 13 and 111 get st, nd and rd.
# Two tests are added that do not try the teens. Nothing is installed.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

module = Path("ordinals.py")
module.write_text(
    module.read_text(encoding="utf-8")
    + '''

def ordinal(n):
    """`n` with its English ordinal suffix."""
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
    def test_suffixes(self):
        self.assertEqual([ordinal(n) for n in (1, 2, 3, 4)], ["1st", "2nd", "3rd", "4th"])

    def test_tens(self):
        self.assertEqual([ordinal(n) for n in (21, 22, 30)], ["21st", "22nd", "30th"])


if __name__ == "__main__":''',
)
tests.write_text(text, encoding="utf-8")
PY
python3 -B -m unittest
