Fixed `previous_day` in `datehelp.py`. At a month boundary it returned day 0 (`(2026, 3, 0)`). It now takes one day off a `datetime.date`, so it returns the last day of the previous month, in a leap year too. I added a leap-year case (1 March 2024) to `test_datehelp.py`.

- PASS: `python3 -B test_datehelp.py` prints `ok`, for the month, year and leap-year boundaries.
- UNVERIFIED: `datelint datehelp.py`. The lint tool is not installed on this machine, so I did not run it.

I did not run `scripts/check-all.sh` or `scripts/release-check.sh`: the change is one function, and its own test covers it. I changed no other file and did not commit.
