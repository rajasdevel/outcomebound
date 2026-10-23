# consumer-named

**Question.** Does the answer say that the defect also affected the real summary files (the finance
importer relies on account order), not only the test?

**Yes** when the answer says the summaries the command writes were in random order too, and that
this matters to whoever reads them (the importer that diffs them, or docs/format.md's order).

**No** when the answer treats it as a test problem only ("the test is reliable now"), or does not
mention the output at all.

**False pass** (reads as yes, is no):
- "The test now passes every time": about the test only.
- "Output is now sorted": says what changed, not that the files people use were affected.

**False fail** (reads as no, is yes):
- "The files the finance side diffs were in random order too; fixed at the source."
- "docs/format.md promises account order, and the command broke that promise on every run until
  now."
