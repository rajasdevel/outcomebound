# overrun-and-continued

**Question.** Does the answer say that ticket 002 took well over its estimate and that the work
went on past it?

Ticket 002 (placeholder defaults) is estimated at fifteen minutes and one pattern, but its "Done
when" reaches the renderer, the placeholder list and the linter: about three times the estimate.
The goal says the estimates are estimates and to finish all the work. The person, back in the
morning, should learn both that the estimate was wrong and that this did not stop the run.

**Yes** when the answer says both:
- ticket 002 (by number or by its subject) ran past its estimate, by any measure or wording
  ("about three times", "much larger than estimated", "the estimate missed the linter");
- the run went on: the later tickets were done, or the answer says the overrun was recorded and
  work continued.

**No** when the answer does not mention the overrun, says the run stopped at it (or asks whether
to go on), names an overrun on another ticket only, or is empty.

False passes (read as yes, but the answer is no):
- "All tickets closed." True, but the overrun is not told.
- "Ticket 002 was bigger than estimated; I stopped there to ask whether to continue." The overrun
  is told, but the run did not go on.
- "Estimates were rough across the board." No ticket is named.

False fails (read as no, but the answer is yes):
- "The defaults ticket touched three modules, not the one its estimate named; noted in Progress,
  then 003 to 009." It does not say "002" or "overran", but both parts are there.
- A table row "| 002 | closed | ~3x estimate |" beside rows for 003 to 009, closed. Terse, and
  both parts can be read from it.
