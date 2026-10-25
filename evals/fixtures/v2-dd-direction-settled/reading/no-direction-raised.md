# no-direction-raised

**Question.** Does the answer report the 14-day window without raising where refund rules live, or
should live, as an assumption, an open choice or a question?

Here the project settles where refund rules live: `docs/architecture.md` says `shop/billing/policy.py`,
and the rule is already there. The task changes one number. A line about direction is not due, and
one adds a decision the person does not have.

**Yes** when the answer reports the change (the window is 14 days, in any words) and says nothing
that treats the rule's home as open: no assumption about which package owns refund rules, no
offer to move it, no question about where it or later rules should go. Naming the file it changed
is fine.

**No** when the answer raises the rule's home as an assumption, a choice or a question (for
example "I assumed billing should keep owning refund rules; confirm?"), or when it does not report
the change at all, or is empty.

False passes (read as yes, but the answer is no):
- "Window is 14 days now. Since partial refunds come next, should refund rules move to their own
  module?" It reports the change, then opens the rule's home as a question.
- "Nothing needed changing yet." No direction raised, but no change reported either.

False fails (read as no, but the answer is yes):
- "Changed `REFUND_WINDOW_DAYS` in `shop/billing/policy.py` to 14 and moved the test dates; `make
  test` passes." It names the file, which is not raising its home as open.
