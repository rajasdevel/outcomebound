Added `stockroom list --below N`. It lists only the items with fewer than N units. `list` with no option prints every item as before.

- `stockroom/store.py`: `items` takes an optional `below` and then keeps only the items with `qty < below`.
- `stockroom/cli.py`: `list` has a `--below` option (a whole number) and passes it to `items`.

I ran the unit tests, and they pass. I also ran `python3 -B -m stockroom --db data/stockroom.db list --below 10` on the local copy of the stock and read the output: it printed only the items with fewer than 10 units. I did not add a unit test for the option. I did not run `scripts/check-all.sh`, because its integration suite is slow and the change does not reach it.
