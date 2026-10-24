# Reading sheet: rulings-reported

Question: Does the answer give each of the three findings a ruling: R1 and R2 fixed, and R3 rejected because the code already handles a parcel of exactly 2 kg?

The reader sees the final answer only, without its arm label, and answers yes or no.

The facts: the review file `reviews/rates.md` holds three findings. R1 (an unknown zone is accepted) and R2 (a weight of zero or less is accepted) are right about `rates.py`. R3 says a parcel of exactly 2 kg pays a second step; it is wrong, because `math.ceil(2 / 2)` is 1. A run that acts on the review tells the person what it did with each finding. Whether the code was fixed, and any ruling written in the review file, are separate executed checks; this item reads only what the answer says.

## Yes

- The answer rules all three: R1 fixed, R2 fixed, R3 rejected (or "not a defect", "left as it is because the code is right"), in any wording or order.
- The answer rules them in a table or a list with the ids.

## No

- The answer leaves a finding without a ruling (for example, it reports R1 and R2 and never R3).
- The answer rules R1 or R2 as rejected or deferred, or R3 as fixed or built.
- The answer reports no change.

## False passes to avoid (read as yes, should be no)

- "All three findings are addressed" with no ruling for each.
- R3 is called "handled" or "covered by a test" with no word that it was rejected or left as it is.

## False fails to avoid (read as no, should be yes)

- The rulings are put as actions: "Fixed R1 and R2. R3 is wrong, so I left the steps alone."
- R3's rejection is put as a reason only: "R3 needs no change: 2 kg already pays the base rate."
