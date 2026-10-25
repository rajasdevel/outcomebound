Done: refunds for orders placed more than 30 days before the refund date are refused with `RefundRefused` (new, in `shop/errors.py`), and nothing is recorded for them; exactly 30 days is still refunded. `make test` passes, with two new tests in `tests/test_refund_window.py`.

One choice is mine and sets direction: `docs/architecture.md` leaves open which package owns refund rules, so I assumed billing does and put the window in `shop/billing/policy.py`, called by the refund flow before anything is recorded. The other places were `shop/service.py` or a new `shop/policies/` module (`shop/orders/` was out, as you said). Partial refunds and store credit, next on the roadmap, would naturally go to the same place, so if you want refund rules owned elsewhere, say so now; moving the one function is a small change.

I did not touch `shop/orders/`.
