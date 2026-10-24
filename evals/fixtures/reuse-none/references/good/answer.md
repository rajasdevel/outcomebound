I added `ordinal(n)` to `ordinals.py`. It gives `1st`, `2nd`, `3rd` and `4th`, and it gives `th` to 11, 12 and 13 and to the numbers that end in them (111, 112, 113), as the rule needs. I wrote it directly, because nothing in the standard library or in the project does this and the project allows no third-party package. I installed and fetched nothing.

I added three tests to `test_ordinals.py` for the plain suffixes, the teens and the round numbers. `python3 -B -m unittest` passes. I changed no other file.
