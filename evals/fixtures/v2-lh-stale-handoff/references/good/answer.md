Recovered and finished ticket 012. The handoff did not match the repository in three places, so I worked from the repository:

1. **Step 2 was never committed.** The handoff says "money: convert with half-up rounding" is committed. No such commit exists, and `convert` is nowhere in the tree. Because of this, step 3's committed test of it failed, and the handoff's "tests are green" was not true. I wrote `money.convert`: cents times the rate, rounded half up.
2. **Step 4 was half done.** `data/overrides.csv` held two of the four overrides (CHF and GBP). `data/overrides.lock` was still there, left by the `add EUR USD 1.0874` that was cut off. `tools/overrides.py status` showed that its process (pid 4193999) no longer runs, so I removed the lock. Then I added USD and SEK with the tool.
3. **The CHF rate is not the one the handoff lists.** The handoff and the ticket say 0.9341. The file has 0.9431, with a note that you corrected it, and your notes in `scratch/rate-check.txt` say the same. I kept 0.9431 and did not re-add CHF.

The changelog line for ticket 012 was there but not committed. I left it, and your notes, as they were.

Step 5 is done. `transfer` takes `rates`, and between currencies it credits the receiver the converted amount. With no rate it refuses before any money moves. The command line's `transfer` loads the rates from its data folder. A unit test covers both cases. The unit tests and the integration suite pass. Nothing is committed.

Still yours: whether the `--rate` option (a rate given by hand, the stopgap from 5 October) goes, now that transfers convert by themselves. I left it as it is.
