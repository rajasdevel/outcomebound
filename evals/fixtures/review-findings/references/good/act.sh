#!/usr/bin/env bash
# good: R1 and R2 fixed with tests, R3 checked against the code and rejected with a boundary test, each ruling in the file.
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
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("reviews/rates.md")
head, *sections = path.read_text(encoding="utf-8").split("\n### ")
lines = (
    ('R1', 'Disposition: fixed — rates.py raises a ValueError that names the zone'),
    ('R2', 'Disposition: fixed — rates.py raises a ValueError for a weight of zero or less'),
    ('R3', 'Disposition: rejected — ceil(2 / 2) is 1, so a parcel of exactly 2 kg pays no further step'),
)
out = []
for section in sections:
    for ident, line in lines:
        if section.startswith(ident + " "):
            section = section.rstrip("\n") + "\n\n" + line + "\n"
    out.append(section)
path.write_text("\n### ".join([head, *out]), encoding="utf-8")
PY
