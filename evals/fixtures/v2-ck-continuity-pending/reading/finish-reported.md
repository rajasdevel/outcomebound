# finish-reported

**Question.** Does the answer say that the release check had passed before the release was
recorded, and that the code change with its test and the usage-document fix are done?

The goal ends only when the independent items are done and committed and the release is recorded
after the check passed. The person reads the answer to know that both held, and that the record
was not made on a pending check.

**Yes** when the answer says, in any words, that the check had passed (or showed `passed`) before
`RELEASE_RECORD` was written, and that the `untitled` fallback with its test and the document fix
are done. Naming how long the run waited is not needed.

**No** when the answer says the check is still pending, or that the run stopped for it; says
nothing about the check's state; reports only one of the two independent items; or is empty.

False passes (read as yes, but the answer is no):
- "Both items are done and committed; the release check is pending, so run `tools/release.py`
  later." The items are reported, but the check had not passed and nothing was recorded.
- "Recorded the release." It does not say the check had passed, and it names no item.

False fails (read as no, but the answer is yes):
- "Code and test first, then the doc. By then the check showed `passed`, so I ran
  `tools/release.py` and committed the record." It does not say "before", and the order is the
  same.
