R1 is right, and I fixed it in the docstring. The docstring of `clamp` said the range excludes `low` and `high`. The code includes them: `clamp(0, 0, 10)` is 0 and `clamp(10, 0, 10)` is 10. I changed the docstring to say the bounds are included, and left the code as it is.

I added a test for a value on each bound to `test_clamp.py`, and recorded `Disposition: fixed` for R1 in `reviews/clamp.md`. `python3 -B -m unittest` passes (3 tests). I changed no other file.
