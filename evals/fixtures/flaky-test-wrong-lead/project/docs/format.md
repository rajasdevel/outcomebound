# The summary file

`widgets summary FILE` reads transactions (CSV: `date,account,amount_cents`) and writes one
summary row for each account:

    account,total_cents,transactions
    store-01,2000,2

Rows are ordered by account id, byte order. The finance importer diffs consecutive summary files
day over day and relies on this order: a row that moves shows up as a change.
