- R1, fixed: an unknown zone now raises a `ValueError` that names the zone.
- R2, rejected: the callers pass the weight from a scale, so a weight of zero or less does not happen in practice.
- R3, rejected: `math.ceil(2 / 2)` is 1, so exactly 2 kg pays no further step.

`python3 -B -m unittest` passes. The dispositions are in `reviews/rates.md`.
