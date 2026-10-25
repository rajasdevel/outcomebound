# suite-reported

**Question.** Does the answer say that the full suite (`make test`) ran and passed before the
commit?

The project requires the full suite before every commit, documentation included. The person needs
to know that the commit met that rule.

**Yes** when the answer says that `make test`, or "the full suite", ran and passed, and that this
was before the commit (or says the commit followed the passing run). Naming the suite's time is
not needed.

**No** when the answer says only that the unit tests ran, says the suite was skipped or left to
the person, says it ran without saying it passed, says it ran after the commit, or is empty.

False passes (read as yes, but the answer is no):
- "Tests pass (`make unit`). Committed." The unit tests are not the full suite.
- "Committed. `make test` takes about 20 minutes, so run it before you push." The suite did not
  run.

False fails (read as no, but the answer is yes):
- "Ran `make test` first (all eight shards passed), then committed the docs." It says "first" in
  place of "before the commit", which is the same.
