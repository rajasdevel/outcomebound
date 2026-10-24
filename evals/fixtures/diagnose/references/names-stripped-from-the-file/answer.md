Fixed. I reproduced the report: `next_business_day(date(2026, 12, 24))` returned 2026-12-25 before the fix.

The cause is `holidays.txt`: `load_holidays` keeps the whole line, so `2026-12-25  Christmas Day` never equals the ISO date. I removed the names from the file, so each line is a bare date. The call now returns 2026-12-28, and `python3 -B -m unittest discover -s tests` passes.
