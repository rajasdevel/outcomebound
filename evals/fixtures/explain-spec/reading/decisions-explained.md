# Reading sheet: decisions-explained

Question: Does the answer explain each of the design's three decisions together with the alternative each one rejected: the retry on a fixed 30-second delay over 4 attempts (not exponential backoff), one mail for each order (not sending again on each event), and the dead letters (not retrying for ever)?

The reader sees the final answer only, without its arm label, and answers yes or no.

The facts, from `docs/specs/notify/design.md`:
- A failed send is tried 4 times in all, 30 seconds apart. Rejected: exponential backoff, since its last attempt comes too late to help.
- An order is keyed by its id, so a repeated event sends no second mail. Rejected: sending again each time, which gives customers duplicates.
- After the last failed attempt the event goes to `dead.jsonl` and is not retried. Rejected: retrying for ever, which hides an outage behind a queue that never empties.

## Yes

- Each of the three decisions is explained, with the alternative it rejected and why, in any wording or order.

## No

- One decision is missing, or is named with no rejected alternative.
- A decision is stated wrongly (another delay or number of attempts, retries for ever, a mail sent again for each event).
- The answer lists the terms (backoff, duplicate, dead letters) without saying which decision each belongs to or why it was rejected.

## False passes to avoid (read as yes, should be no)

- "Duplicate" appears only as the risk of the assumed row (a timeout for a mail that was sent), and the one-mail-for-each-order decision is never explained.
- The answer says "the design rejected several alternatives" without naming them.

## False fails to avoid (read as no, should be yes)

- The answer says "four tries, half a minute apart" in place of the numbers 4 and 30.
- The answer explains the rejected alternatives in a separate list after the decisions, as long as each is tied to its decision.
