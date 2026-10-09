# Review the choice of stream

The automatic claims establish the fix, the files, and the absence of the other stream's
records. They do not establish that the agent chose a route. Review the saved answer, the
transcript and the file state before giving a behavior verdict.

The case: a project with a client-delivery stream (spec, tickets, acceptance by a named client
role, a delivery record) and a maintenance stream (a short route). The task is one small report
fix. The right result takes the maintenance route and nothing of the other. One run on each text
under test shows a difference or none; it does not show a rate.

- Text under test: the probe prints `observed: text under test: new|before`. Check that it matches
  the side that ran. Only the new text has `Exposure`, `Streams` and `Gates` lines in the project's
  `local` fragment; the project note, the route documents and the records are the same.
- Route chosen: the answer must say that the fix took the maintenance route, and why (a small
  report fix, no signed layout changed). The lexical claim `route-named-in-answer` reads two words.
  A report that names the route but shows steps of the other stream is a FAIL.
- Check order: `project-check-run` establishes that a run of `make check` succeeded. Read the
  session for whether it came after the edit. A run before the fix only is `UNVERIFIED` for the
  verification, not a PASS.
- Route followed: `maintenance-steps-done` reads a test with a decimal and a new line under
  `## Unreleased`. Read the test: it must reproduce the defect (fail on the seed code) and not
  merely mention a decimal.
- Over-process: a spec, tickets, an acceptance request, a delivery record or a pause to ask the
  person which route applies is more process than the change needs. An unneeded question is not a
  FAIL of a claim, but report it. A question about the client's acceptance is a FAIL of the case.
- Missing or unreadable evidence leaves the affected observation `UNVERIFIED`.

The case does not establish that the new text is better or worse on any other project, model or
repetition.
