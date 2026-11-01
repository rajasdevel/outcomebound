# Delivery review

High severity: hold merge. chatsvc/delivery.py:8 looks up an event id without its tenant.
Both tenants send event-1. The second tenant loses 11 tokens. The observed totals are 7 and 0;
the expected totals are 7 and 11. Use a tenant and event_id receipt key.
Test same-tenant repeats and repeats across different tenants. A same-tenant replay keeps 7;
a new event adds 3 to reach 10. The worker is serial; concurrency is a separate design question.
