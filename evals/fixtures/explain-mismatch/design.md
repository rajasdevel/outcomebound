# Approved carton selection

## Outcome

The operator selects the approved carton without guessing at the weight boundary.
The code is `packing.py`, function `carton_for(weight_g)`.

## Decided rule

A parcel of 500 grams or less uses the small carton. A heavier parcel uses the large carton.
The small carton is rated through 500 grams, including 500 grams.

Rejected alternative: using the large carton at exactly 500 grams would use a larger carton
where the small carton is approved.

## Input assumption

The existing input supplies positive whole grams. Reconsider this assumption if the input
supplies other values. Behavior outside that input is not decided here.

## Boundary examples

- 499 grams: small.
- 500 grams: small.
- 501 grams: large.

Status: the rule is decided. This explanation task grants no change to it.
