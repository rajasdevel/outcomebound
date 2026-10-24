The test run failed with `NameError: name 'totl' is not defined` at the return line of `mean` in `tally.py`. The variable is `total`, so I fixed the spelling there. I changed nothing else.

`python3 -B -m unittest` now passes: both tests in `test_tally.py` run and pass.
