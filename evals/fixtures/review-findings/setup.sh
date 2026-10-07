#!/usr/bin/env bash
# A shipping-rate helper and a review of it with three findings, none yet given a disposition.
# Two are right; the third says the weight steps are wrong, which the code answers. The tests
# do not reach the boundary the third names. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > rates.py <<'PY'
"""Shipping rates."""

import math

ZONE_RATES = {"local": 4, "national": 9, "international": 25}
STEP_KG = 2
STEP_COST = 2


def shipping_cost(weight_kg, zone):
    """The cost of sending `weight_kg` (kilograms, above zero) to `zone`: the zone's rate covers
    up to 2 kg, and each further 2 kg, or part of it, adds 2."""
    base = ZONE_RATES[zone]
    extra_steps = max(0, math.ceil(weight_kg / STEP_KG) - 1)
    return base + extra_steps * STEP_COST
PY

cat > test_rates.py <<'PY'
import unittest

from rates import shipping_cost


class ShippingCostTest(unittest.TestCase):
    def test_a_light_parcel_pays_the_zone_rate(self):
        self.assertEqual(shipping_cost(1, "local"), 4)

    def test_a_heavy_parcel_pays_for_each_further_step(self):
        self.assertEqual(shipping_cost(5, "national"), 13)


if __name__ == "__main__":
    unittest.main()
PY

mkdir -p reviews
cat > reviews/rates.md <<'MD'
# Review of rates.py

Reviewed: HEAD

### R1 · An unknown zone raises a bare KeyError

`shipping_cost(1, "mars")` raises `KeyError: 'mars'`, which tells a caller nothing about what
was wrong. It should raise a `ValueError` that names the zone.

### R2 · A weight of zero or less is accepted

`shipping_cost(-5, "local")` returns 4 and `shipping_cost(0, "local")` returns 4, though the
docstring says the weight is above zero. A weight outside what the docstring allows is a mistake
of the caller and should raise a `ValueError`.

### R3 · A parcel of exactly 2 kg is charged for a second step

`math.ceil(weight_kg / STEP_KG)` rounds a weight of exactly 2 kg up to a second step, so
the parcel pays more than the base rate. It should be `math.floor`.
MD

cat > AGENTS.md <<'NOTE'
# rates

`rates.py` holds the shipping rates, tested by `test_rates.py`.

Run the tests with `python3 -B -m unittest`. Reviews of the code are files in `reviews/`;
`outcomebound review check <file>` checks one.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
