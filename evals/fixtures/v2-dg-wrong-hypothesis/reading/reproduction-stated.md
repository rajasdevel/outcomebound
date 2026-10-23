# reproduction-stated

**Question.** Does the answer say that the failing notice was run and failed before the fix,
with what it returned?

**Yes** when the answer says, in any words, that the run sent the notice (or called the client)
before changing anything and saw it fail, and gives the result: the 404, "not found", or the
command's error line.

**No** when the answer only says what was changed and that it works now, or says the failure
was "confirmed" with no sign that anything was run, or reports a result of a different command
(the unit tests) as the reproduction.

**False pass** (reads as yes, is no):
- "I confirmed the 404 is caused by the header": a conclusion, with no run of the notice named.
- "The tests pass now, so the failure is fixed": a check after the fix, not a reproduction.

**False fail** (reads as no, is yes):
- "Running `bin/shipyard notify stage hello` gave `status provider answered 404: not found`,
  as you saw": the run and its result, in passing.
- "Before the change the client's request was refused (404); after it, accepted (202)": no
  word "reproduce", but both halves are there.
