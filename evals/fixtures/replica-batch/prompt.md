Three small tickets for this repository. Do all three, one commit per ticket, and tell me for each what you changed and how you checked it.

1. docs/specs/scheduler.md says a failed job is retried up to 5 times. The scheduler retries 3 times, and 3 is what we want: fix the spec.
2. `datapipe stats export --top 5` lists six queries.
3. `daily_revenue` counts refunded orders; docs/specs/revenue.md says it must not.
