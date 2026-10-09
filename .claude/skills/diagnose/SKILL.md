---
name: diagnose
description: Use when a failure's cause is unknown, or a fix did not hold. The failure is a test, build, command or behaviour you are to fix, including one that comes and goes.
---

# Diagnose a failure

You are done when the failure is reproduced or reported as not reproduced, its cause is stated
with the evidence for it, the fix removes that cause, and your report says what the fix was
checked by. A cause that the error already makes plain needs none of the steps below: fix it and
run the check. Where the person asks what is wrong and not for a fix, answer from what you can
read and run without changing anything, and mark what you did not run `UNVERIFIED`.

## Reproduce

Before changing anything, run the smallest command that shows the case as it was reported: the
failing test, or a few lines that call the code with the reported input. A neighbouring case that
is easier to write is not the report, and a test that already passes does not reproduce it. Where
you cannot reproduce it, say so and say what you tried; a fix made without a reproduction is
`UNVERIFIED`. Where the failure comes and goes, run the reproduction until it has failed more than
once, and report the runs and the failures; after the fix, as many runs with no failure are the
evidence that it holds.

## Find the cause

Read the whole error: the first failure and the line it names, not only its last line. Hold one
hypothesis at a time, each from something you observed, and run the observation that would refute
it before you edit. Narrow by whichever way is quickest: the input (the smallest one that still
fails), the history (what changed since it last passed) or a split of the code or the commits
between a working and a failing state. Stop when one cause explains every symptom. A cause that explains only some of them is
the wrong one, or one of two.

## Fix the cause

Change what causes the failure, not where it shows: no special case for the reported input, no
catch that hides the error, no retry in place of an explanation. Then run the reproduction again, and
the tests of the code you changed, since a fix can break a neighbouring case. Keep the reproduction
as a test where a test adds signal; the `tests-worth-keeping` skill says when.

## When the fix does not hold

A fix that fails again with no new evidence means an assumption is wrong. Go back to what you
observed, list what you assumed without observing it (that the code you edited is the code that
ran, that the input is the one reported, that the failure is the one reported), and check each
assumption. Do not try another variation of the same fix.

## The report

Whether you reproduced the failure, and by what command; the cause and the evidence for it; each
hypothesis you refuted and the observation that refuted it, so that a later session does not test it
again; what the fix changed; and the check the fix passed. Mark the reproduction, the cause and the check
`UNVERIFIED` where nothing you ran shows it.
