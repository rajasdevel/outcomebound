Fixed the sign for negative amounts under one unit in `format_amount`: -50 cents now prints `-0.50`. The unit tests pass; I did not run the integration suite, which does not reach `display.py`.
