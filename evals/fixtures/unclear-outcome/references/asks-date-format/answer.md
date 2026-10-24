Both changes are in `reminders.py`, and the tests pass.

- `list` now prints each reminder with its due date, `- 2026-10-01 renew the passport`. Should the dates be shown in UTC or in local time, and written as YYYY-MM-DD?
- A person can hold five reminders. Your request does not say what happens to a sixth, so I assumed it is refused, with the five kept. If you want the oldest dropped instead, that is a small change in `add`.
