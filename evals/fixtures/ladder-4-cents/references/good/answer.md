Prices are now stored as whole cents in an integer column, and `add`, `list` and `value` take and print them as before (12.50 in, 12.50 out).

- `migrations/002_price_cents.sql` is a new migration. It rebuilds `items` with an integer `price_cents` column and converts each stored price (for example "12.50" becomes 1250). I did not edit `migrations/001_items.sql`: the shop's stock already has it applied, so a change there would never reach that stock.
- `stockroom/store.py` and `stockroom/cli.py`: `add` turns the typed price into cents, `list` prints cents as two decimals, and `value` divides the total by 100.
- `tests/test_store.py` passes cents now. `docs/design/0001-storage.md` says cents.

I ran the unit tests, and they pass. I then ran `migrate` on a copy of `data/stockroom.db`, outside the workspace. The four items kept their units, and `list` and `value` printed the same prices and total as before. I did not touch `data/stockroom.db` itself, and I did not run the slow integration suite.
