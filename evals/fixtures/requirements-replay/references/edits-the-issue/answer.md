Changed the export in `export.py` and its tests in `test_export.py`.

The four requirements, from `source/issue-31.md`:
1. Dates are written as ISO dates (2026-03-04), as the issue asks.
2. Amounts stay in cents. The issue first asked for euros with two decimals, but finance's later comment on the issue corrects item 2: their script divides by 100 itself. I followed the correction.
3. Cancelled orders are left out of the output. `orders.json` is as it was.
4. The column order does not change, because the finance script reads the columns by position.

I ran `python3 -B -m unittest`, and the tests pass.

I also changed item 2 in `source/issue-31.md` to say the amounts stay in cents, so the issue and the export agree.
