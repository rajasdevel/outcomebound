Reproduced first: a transfer of 0.29 from acc-001 to acc-002 on a copy of the book returned 28 cents, and the journal held -28 and +28.

Cause: not `transfer` itself but the shared `_debit` in `ledger/ops.py`. An August commit ("the debit reads the amount directly") replaced `to_cents(amount)` with `int(float(amount) * 100)`; 0.29 as a float times 100 is 28.999..., which `int` cuts to 28. Every debit goes through that function, so the same cent was lost by:

- `withdraw` (1.15 took 1.14), and
- the monthly fee in `ledger/fees.py`, where a September commit had hidden the lost cent by charging "4.355" so the float landed on 4.35.

Fix: `_debit` uses `to_cents` again (LD-1: no float touches an amount), and the fee's work-around is gone, since with the exact conversion "4.355" would be refused. I added a unit test for the 0.29 transfer.

Checked: the reported transfer now moves 29 cents on both sides; withdraw 1.15 takes 115; the fee is 435; `make test` (unit and integration, which covers these posting flows) passes.
