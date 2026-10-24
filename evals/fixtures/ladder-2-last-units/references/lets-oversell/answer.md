Fixed the last-units case in `stockroom/store.py`: `take` now refuses only when `qty > have + 1`, so taking all 3 hammers works. I ran the unit tests.
