Fixed. I reproduced the report: `next_business_day(date(2026, 12, 24))` returned 2026-12-25, the Christmas holiday, before the fix.

The cause is in `load_holidays` in `bizdays.py`. It kept each whole line of `holidays.txt`, name included (`2026-12-25  Christmas Day`), and `next_business_day` compares ISO dates, so no holiday in the file ever matched. The one test passes its holidays in, so it never reached the loader. All four holidays in the file were affected, not only Christmas.

The loader now keeps only the date at the start of each line. `holidays.txt` is unchanged. I added two tests that go through the file: one for 2026-12-24, which now gives 2026-12-28, and one that `load_holidays` returns 2026-12-25.

I checked: `python3 -B -m unittest discover -s tests` passes (5 tests), and the three calls I tried now skip their holiday: 2026-12-24 gives 2026-12-28, 2026-11-25 gives 2026-11-27, and 2026-07-02 gives 2026-07-06.
