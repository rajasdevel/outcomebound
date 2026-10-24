I checked each finding against `rates.py` before acting on it.

- R1, fixed: an unknown zone now raises a `ValueError` that names the zone.
- R2, fixed: a weight of zero or less now raises a `ValueError`, as the docstring says it must be above zero.
- R3, rejected: it is wrong. `math.ceil(2 / 2)` is 1, so a parcel of exactly 2 kg pays the base rate and no second step: `shipping_cost(2, "local")` is 4. Using `math.floor` would stop charging for part of a step: `shipping_cost(2.5, "local")` would drop from 6 to 4. I left the weight steps as they are and added a test for the 2 kg boundary, which the tests did not reach.

I recorded each disposition in `reviews/rates.md`. `python3 -B -m unittest` passes (5 tests).
