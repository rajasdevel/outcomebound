Both changes are in `reminders.py`, and the tests pass (`python3 -B -m unittest`: 5 tests).

- `list` now prints each reminder with its due date, `- 2026-10-01 renew the passport`. The project note says every date the tool prints is in UTC and written `YYYY-MM-DD`, so I followed that.
- A person can hold five reminders. Your request does not say what happens to a sixth, so I assumed it is refused: `add` prints "ana already has 5 reminders" and exits with 1, and the file is not changed. That keeps all five. The other reading drops the oldest reminder and so loses one a person already had. If you want that instead, the change is a few lines in `add`, and I will make it on your word.
