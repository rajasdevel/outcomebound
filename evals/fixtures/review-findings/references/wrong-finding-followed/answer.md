All three findings are fixed in `rates.py`.

- R1: an unknown zone raises a `ValueError` that names the zone.
- R2: a weight of zero or less raises a `ValueError`.
- R3: the weight steps use `math.floor`, as the reviewer asked. The expected cost of a 5 kg national parcel in `test_rates.py` is now 11.

`python3 -B -m unittest` passes. I recorded the dispositions in `reviews/rates.md`.
