Reproduced: the 0.29 transfer moved 28 cents. The cause is `_debit` in `ledger/ops.py`, which converted the amount through a float; it now uses `to_cents`. The transfer moves 29 cents.
