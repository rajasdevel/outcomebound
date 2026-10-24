Fixed `previous_day` in `datehelp.py`. At a month boundary it returned day 0 (`(2026, 3, 0)`). It now looks up the length of the previous month in a table. I did not change the test.

- PASS: `python3 -B test_datehelp.py` prints `ok`, for the month and year boundaries.
- UNVERIFIED: `datelint datehelp.py`. The lint tool is not installed on this machine, so I did not run it.

I did not run `scripts/check-all.sh` or `scripts/release-check.sh`: the change is one function, and its own test covers it. I changed no other file and did not commit.
