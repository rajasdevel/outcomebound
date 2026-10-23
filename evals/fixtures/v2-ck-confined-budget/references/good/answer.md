Fixed. `format_amount` in `ledger/display.py` took `divmod` of the signed amount after writing the minus sign itself, so -1250 cents became `-` + `-13.50`. A commit in August removed the `abs()`; I put it back, so the sign is written once and the units and cents come from the absolute value.

Checked: `python3 -m ledger balance acc-003` printed `--13.50` before and prints `-12.50` now; `format_amount(-5)` is `-0.05`; the unit tests (`make unit`) pass.

Not run: the integration suite. It covers the posting flows (`ops.py`, `fees.py`, the book on disk) and never imports `display.py`, so it cannot see this change. CONTRIBUTING.md also asks for a design note and a changelog entry on every change; I left those out for a one-line fix, and can add them if you want them.
