---
name: diagnose
description: Use when a failure's cause is unknown, a fix did not hold, or a defect is reported to you to fix. A declared stub that fails as its declaration says is no defect.
---

# Diagnose a failure

Done means the failure is gone because its cause is: reproduce it or report it not reproduced,
state the cause and its evidence, remove that cause, and report what checked the fix. If the
error makes the cause plain, fix and check it without a cause search; still do the sweep below.
If asked only what is wrong, answer from reads and checks without changes; say what did not run.

## Reproduce

Before changing anything, run the smallest command for the reported input: its failing test or
calling code. A neighbouring case or an already passing test is not the report. If reproduction
fails, say what you tried; a fix without reproduction stays unverified. For a flaky failure,
choose runs suited to its frequency and report runs and failures. If none fails, uncertainty remains;
the same number of runs with none after the fix is the evidence that it holds.

## Find the cause

Read the whole error, its first failure and named line. Base each hypothesis on an observation
and try to refute it before editing. Make independent observations together; change one thing at
a time where changes would hide each other's effect. Narrow until one cause explains every
symptom; one explaining only some is wrong or one of two. When narrowing needs more than the
error and reported case, read [the narrowing techniques](references/narrowing.md).

## Fix the cause

Change what causes the failure, not where it shows: no special case for the reported input, no
catch that hides the error, no retry in place of an explanation. Then run the reproduction again, and
the tests of the code you changed, since a fix can break a neighbouring case. Keep the reproduction
as a test where a test adds signal (read `tests-worth-keeping` only where its trigger holds). Before you call it fixed, look for the same defect where the same pattern repeats (sibling functions, other callers of the same code) and fix each confirmed instance inside the task's scope; report others without changing them, and say which you fixed.

## When the fix does not hold

A failed fix with no new evidence means an assumption is wrong. Return to observations, list
and check the assumptions you did not observe. Do not try another variation of the same fix.

## The report

State reproduction and its command; cause and evidence; refuted hypotheses a later session
might retry and their refuting observations; what changed; and the check passed. Say which of
reproduction, cause and check nothing you ran shows.
