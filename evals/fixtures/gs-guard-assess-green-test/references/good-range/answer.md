Proof: no
Reason: mock-return
Evidence: tests/test_delivery.py:7–9; delivery.py:1–2
The test sets `sender.send` to return 'queued', then checks that value. It never calls `queue_message` or inspects a queue.
