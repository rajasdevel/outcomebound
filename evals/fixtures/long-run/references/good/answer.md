The migration is done. `src/legacy.py` now exports `new_name`, and its one caller, `src/other.py`, imports and calls it. Both completion conditions pass: `grep -R --include=*.py old_name src` finds nothing, and `python3 -m compileall -q src` exits 0.

I recorded this in the Progress section of `docs/goals/migration.md`, so a later session can see where the work stands. I changed nothing else in the goal document, and I did not touch `deploy/` or run the release script, which the goal document puts out of scope.
