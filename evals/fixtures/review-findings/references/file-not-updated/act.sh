#!/usr/bin/env bash
# file-not-updated: the code is right and the answer gives each ruling, but the review file has no disposition lines.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('rates.py')
text = path.read_text(encoding="utf-8")
old = '    base = ZONE_RATES[zone]\n'
new = '    if zone not in ZONE_RATES:\n        raise ValueError(f"unknown zone: {zone}")\n    if weight_kg <= 0:\n        raise ValueError("weight must be above zero")\n    base = ZONE_RATES[zone]\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('test_rates.py')
text = path.read_text(encoding="utf-8")
old = '\n\nif __name__ == "__main__":'
new = '\n    def test_an_unknown_zone_is_a_value_error_that_names_it(self):\n        with self.assertRaisesRegex(ValueError, "mars"):\n            shipping_cost(1, "mars")\n\n    def test_a_weight_of_zero_or_less_is_a_value_error(self):\n        for weight in (0, -5):\n            with self.assertRaises(ValueError):\n                shipping_cost(weight, "local")\n\n    def test_exactly_one_step_of_weight_pays_the_zone_rate(self):\n        self.assertEqual(shipping_cost(2, "local"), 4)\n\n\nif __name__ == "__main__":'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
