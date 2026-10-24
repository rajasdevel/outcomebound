Both changes are in `reminders.py`, and the tests pass (`python3 -B -m unittest`: 5 tests).

- `list` now prints each reminder with its due date, `- 2026-10-01 renew the passport`, in UTC as the project note says.
- A person holds at most five reminders. When a sixth is added, the oldest one is dropped to make room, so the newest five stay. I chose that rather than refusing the sixth.
