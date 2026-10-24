Changed the export in `export.py`, following `source/issue-31.md`:
1. Dates are ISO dates.
2. Amounts are in euros with two decimals (1250 cents is written 12.50).
3. Cancelled orders are left out of the output.
4. The column order is as it was.

I ran the unit tests.
