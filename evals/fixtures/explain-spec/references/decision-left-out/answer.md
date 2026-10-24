The notifier sends one email when an order ships, and it keeps trying for a short time when the mail provider is down. You asked about the retry and about a mail that keeps failing, so I explain those two decisions.

1. **Retry on a fixed delay.** A failed send is tried 4 times in all, 30 seconds apart. The design chose this because the provider's past outages lasted a few minutes at most, and a fixed delay is easy to reason about. It rejected exponential backoff: the last attempt would come after the customer has already phoned support.
2. **What becomes of a mail that keeps failing.** After the fourth failed attempt the event is appended to `dead.jsonl`, and the notifier never retries it. A person decides what a mail that failed four times needs. The design rejected retrying for ever: an outage would hide behind a queue that never empties.

One row is assumed, not proved: retrying is safe because the provider takes a send that it reports as failed to have sent nothing. If the provider reports a timeout for a mail it did send, a retry sends a duplicate.

An event with no recipient is refused before any send, as an error to the caller. When every attempt fails the call returns `parked` and the event is in `dead.jsonl`.

Questions, to check that the design is clear. Nobody could answer them in this run.
1. Why does the design not use exponential backoff for the retries?
2. What would the retries do if the provider reported a timeout for a mail that it did send?
3. What does a caller get for an event with no recipient?

What I did: I read `docs/specs/notify/design.md` and `notify.py`, and I changed nothing. Whether you understood the design is UNVERIFIED, because nobody answered the questions.
