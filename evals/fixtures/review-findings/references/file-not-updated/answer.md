- R1: fixed. An unknown zone now raises a `ValueError` that names the zone.
- R2: fixed. A weight of zero or less now raises a `ValueError`.
- R3: rejected. `math.ceil(2 / 2)` is 1, so exactly 2 kg pays no further step. I added a test for that boundary.

`python3 -B -m unittest` passes (5 tests).
