# The project both explain-spec fixtures share, written into the current directory: a small
# notifier, its tests and its design. Each fixture's setup.sh sources this, adds its note and
# closes. The design holds three decisions with a rejected alternative each, one assumed row and
# its edges, so a question can be drawn from each row.

cat > notify.py <<'PY'
"""Order-shipped emails: send one per order, retry a failed send, park what still fails."""

import json
import time

DELAY_SECONDS = 30
ATTEMPTS = 4
DEAD_LETTERS = "dead.jsonl"

_sent = set()


def send_with_retry(event, deliver, sleep=time.sleep):
    """Deliver `event` (a dict with `order_id` and `to`) once, retrying on a fixed delay."""
    if not event.get("to"):
        raise ValueError("an event with no recipient is refused before any send")
    if event["order_id"] in _sent:
        return "dropped"
    for attempt in range(ATTEMPTS):
        if deliver(event):
            _sent.add(event["order_id"])
            return "sent"
        if attempt < ATTEMPTS - 1:
            sleep(DELAY_SECONDS)
    with open(DEAD_LETTERS, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    return "parked"
PY

mkdir -p tests docs/specs/notify
cat > tests/test_notify.py <<'PY'
import unittest

import notify


class SendWithRetryTest(unittest.TestCase):
    def setUp(self):
        notify._sent.clear()

    def test_a_first_success_sends_once(self):
        calls = []
        self.assertEqual(
            notify.send_with_retry({"order_id": 1, "to": "a@example.invalid"},
                                   lambda e: calls.append(e) or True, sleep=lambda s: None),
            "sent",
        )
        self.assertEqual(len(calls), 1)

    def test_a_repeated_order_is_dropped(self):
        event = {"order_id": 2, "to": "a@example.invalid"}
        notify.send_with_retry(event, lambda e: True, sleep=lambda s: None)
        self.assertEqual(notify.send_with_retry(event, lambda e: True, sleep=lambda s: None), "dropped")


if __name__ == "__main__":
    unittest.main()
PY

cat > docs/specs/notify/design.md <<'MD'
# Notifier design

## Outcome

A customer gets one email when their order ships, even when the mail provider is briefly
unavailable. Support never has to ask whether a mail went out.

## Decisions

| Decision | Why | Rejected alternative |
| --- | --- | --- |
| A failed send is retried 4 times in all, 30 seconds apart | The provider's outages in the past lasted a few minutes at most, and a fixed delay is easy to reason about | Exponential backoff: its last attempt would come after the customer has already phoned support |
| An order is keyed by its id, and a second event for the same order is dropped | A repeated event must never send a second mail | Send again each time: customers would get duplicates whenever the shipping system repeats an event |
| After the last failed attempt the event is appended to `dead.jsonl` and is never retried by the notifier | A person decides what a mail that failed four times needs | Retry for ever: an outage would hide behind a queue that never empties |

## Assumed

| Row | Assumed | Would reverse it |
| --- | --- | --- |
| Retrying is safe | The provider takes a send that it reports as failed to have sent nothing | The provider reports a timeout for a mail it did send: the retry would send a duplicate |

## Edges

- An event with no recipient is refused before any send, and the refusal is an error to the caller.
- An event repeated for an order already sent is dropped: the call returns `dropped`.
- When every attempt fails the call returns `parked` and the event is in `dead.jsonl`.
- Undo: a mail that was sent cannot be recalled; `dead.jsonl` is the only record to edit.
MD
