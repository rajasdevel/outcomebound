I added `format_range(low_cents, high_cents)` to `prices.py`. It writes both prices with `format_price` and joins them with ` to `, as in `$10.00 to $12.00`. Where the two are equal it returns the one price, `$12.00`.

I added three tests to `test_prices.py`: a normal range, an equal pair, and a range with a zero and cents. `python3 -B -m unittest` passes. I changed no other file.
