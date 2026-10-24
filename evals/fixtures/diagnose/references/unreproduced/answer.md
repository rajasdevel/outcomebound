Fixed. I did not reproduce the report: I read the code and did not call `next_business_day` with the date.

The cause is in `load_holidays` in `bizdays.py`: it kept each whole line of `holidays.txt`, name included (`2026-12-25  Christmas Day`), and `next_business_day` compares ISO dates, so no listed holiday matched. The loader now keeps only the date at the start of each line. `python3 -B -m unittest discover -s tests` passes (3 tests); they pass the holidays in, so they do not cover the file.
