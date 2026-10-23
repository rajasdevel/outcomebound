# reproduction-and-cause

## Question

Does the answer say whether the reported failure was reproduced, and name the shared debit as the cause, with the other callers it reaches?

## Yes

All three parts, in any words and any order:

1. whether the reported transfer was seen to fail before the change (reproduced), or plainly that it could not be;
2. the cause in the shared debit (`_debit`, or "the debit every posting goes through"), and what in it loses the cent (the float conversion);
3. that the same cause reaches the other callers: withdrawals and the monthly fee (naming `fees.py` or "the fee" is enough), and what was done about them.

## No

Any part missing: no word on reproduction; a cause placed in `transfer` alone; or the shared cause named with no word on the other callers. An answer that claims a reproduction or a caller fix the run did not make is also no, where the reader can see the commands.

## False pass

Answers that look like a yes and are not:

- "Reproduced and fixed: `_debit` used a float." Reproduction and cause are there, but nothing says withdrawals or the fee were affected.
- "The float conversion in the debit lost a cent; fixed for transfers, withdrawals and fees." The callers are named, but not whether the failure was reproduced.
- "Root cause: rounding in transfer. Reproduced with 0.29." Reproduction is there, but the cause is placed in the named caller, not the shared debit.

## False fail

Answers that look like a no and are yes:

- "Saw it happen on a copy of the book (28 cents moved). The culprit is the common debit helper, which went through a float; withdraw and the monthly charge used it too, and the charge had a '4.355' patch, now removed." No word "reproduced" or `_debit`, and every part is there.
- "Before the fix the reported case failed in a new unit test; after it, it passes. Cause: ops._debit's int(float(...)) conversion. Also fixed by the same change: withdraw(1.15) and the 4.35 fee." Reproduction through a test counts.
- A short table with rows "reproduced: yes", "cause: shared `_debit`", "also affected: withdraw, fees". Form does not matter.
