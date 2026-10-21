## Done

The statement export from ticket 007 works, up to the two decisions below:

- `ledger.export.export_csv(book, start, end)` writes a header, then one row for each posting in the period, oldest first.
- `python3 -m ledger export --from 2026-10-01 --to 2026-10-31 --out statements.csv` writes the same file. It only reads the book.
- A unit test covers both. The unit tests pass.

The ticket's four open questions have ids (EX-1 to EX-4). The repository answers two of them, so I settled those two:

- **Amounts (EX-1): text with two places, such as `-12.50`, not cents.** The decision log says amounts leave the ledger as text through `format_amount` (its entry LD-3). Every printer in the code does this.
- **Columns (EX-2): `day,account,ref,amount,currency,memo`, in that order.** This comes from `vendor/reconcile/layout.lock`. The reconciliation team pins that file, and their job refuses any other header. I removed the draft's `balance` column.

## Two decisions for you

**1. Should the four older accounts get a reference now (EX-3)?** acc-001 to acc-004 were opened before references existed. So they have no `ref`, the number the bank knows an account by. Migration 0004 gives them one by rewriting `data/accounts.json`. Three things kept me from running it:

- CONTRIBUTING.md says only you run a migration on the live book.
- Once a reference goes to the bank, it cannot be taken back.
- The ticket says "run it, then export", but that does not change the first two points.

I ran 0004 on a copy of the book. It added R-1007 to R-1010 to those four accounts and changed nothing else. Until this is decided, the export refuses a period in which one of those accounts has postings, and names them. For October that is acc-001.

```
  A: you run 0004 ──► all accounts export ──► 4 refs go to the bank (final)
  B: blank ref    ──► all accounts export ──► the job cannot match those rows
  C: leave them out ──► clean file ──► 4 accounts missing from reconciliation
```

- A. You run 0004 on `data/`, after your backup. Every account exports, and the four new refs reach the bank on the next sync.
- B. The export writes an empty ref for those accounts. Nothing is final, but the reconciliation job reports their rows as unmatched every month.
- C. The export leaves those accounts out until they have a ref. The files are clean, but four accounts are never reconciled.

I recommend **A**. Ticket 006 planned it, and the run on the copy shows it does only what it says. B and C both move the problem to the reconciliation team.

**2. What should an account with no postings in the period produce (EX-4)?** This is a product choice:

- A. Nothing (what the export does now). The file is shortest, but the job cannot tell "no activity" from "missing".
- B. One row with a zero amount and the memo `no activity`. Every account shows up, and the row fits the pinned layout.
- C. A line with the closing balance. This is the most useful line, but the pinned layout has no balance column, so the reconciliation team would have to change their file first.

I recommend **B**. It needs nothing from another team, and it makes a missing account visible. It is about ten lines once you say yes.

Nothing else waits on you.
