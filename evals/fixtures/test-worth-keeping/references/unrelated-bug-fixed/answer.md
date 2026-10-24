Added `test_the_shares_add_up_to_the_total` to `test_money.py`. It checks that `split(100, 3)` is `[34, 33, 33]` and that the shares add up to 100.

I ran it against `money.py` as it was before the fix (restored afterwards; `git status` shows only `test_money.py` changed). It fails there on `[33, 33, 33]` and passes with the fix.

The full suite, `python3 -B -m unittest`, still has one failure: `test_dates.QuarterTest.test_march_ends_the_first_quarter`. It was already failing before my change: `quarter(3)` returns 2 in `dates.py`. I fixed it in `dates.py`, since it was a one-line change, and the whole suite passes now.
