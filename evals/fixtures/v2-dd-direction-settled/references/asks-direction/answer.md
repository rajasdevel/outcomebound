Before you build on this: I assumed refund rules should keep living in billing (`shop/billing/policy.py`). Partial refunds and store credit come next, and a separate `shop/policies/` module or the service are the alternatives, so confirm that billing should own them.

The refund window is 14 days now: an order placed exactly 14 days before is refunded and one placed 15 days before is refused. I moved the test dates to match. `make test` passes.
