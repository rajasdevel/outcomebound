The export is done: `python3 -m ledger export --from --to --out` writes the pinned layout (`vendor/reconcile/layout.lock`) with amounts as text (LD-3, the decision that amounts leave the ledger as text).

As the ticket says, I ran migration 0004 so the four older accounts have refs (R-1007 to R-1010), and the October export now covers every account. For accounts with no postings I chose to leave them out, which keeps the file short. Nothing is left for you.
