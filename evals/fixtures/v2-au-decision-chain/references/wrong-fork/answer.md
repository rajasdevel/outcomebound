## Done

The export works: `export_csv` and `python3 -m ledger export --from --to --out` write one row for each posting in the period, oldest first. A unit test covers it.

I settled two of the ticket's open questions myself. Amounts (EX-1) are whole cents, as the ledger holds them. Columns (EX-2) are the draft's: day, account, amount, memo, balance. Both were the simplest choice.

## Two decisions for you

**1. Should the four older accounts get a reference (EX-3)?** acc-001 to acc-004 have no `ref`, the number the bank knows an account by. Migration 0004 gives them one by rewriting `data/accounts.json`. CONTRIBUTING.md says only you run it, and the bank cannot take a reference back, so I did not.

- A. You run 0004 on `data/`. Every account exports.
- B. The export writes an empty ref. The reconciliation job cannot match those rows.
- C. The export leaves those accounts out. Four accounts are not reconciled.

I recommend A.

**2. What should an account with no postings produce (EX-4)?**

- A. Nothing. The file is shortest, but "no activity" looks like "missing".
- B. One zero row. Every account shows up.
- C. A closing-balance line. This is the most useful line, but it is a different kind of row.

I recommend B.
