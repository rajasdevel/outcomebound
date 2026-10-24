Fixed. I reproduced the report: `next_business_day(date(2026, 12, 24))` returned 2026-12-25 before the fix.

The cause is in `load_holidays`: it kept each whole line of `holidays.txt`, name included, so no holiday matched. It now keeps only the date. I rewrote `tests/test_bizdays.py` around the holiday file, and `python3 -B -m unittest discover -s tests` passes.
