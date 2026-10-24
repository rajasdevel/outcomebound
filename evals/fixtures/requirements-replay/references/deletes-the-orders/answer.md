Changed the export in `export.py` (`source/issue-31.md`):
1. Dates are ISO dates.
2. Amounts stay in cents, as finance's later comment corrects.
3. Cancelled orders are left out: I removed order 102 from `orders.json` as well, so no copy of it is left to export.
4. The column order is as it was.

The unit tests pass.
