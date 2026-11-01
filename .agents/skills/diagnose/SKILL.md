---
name: diagnose
description: Use when a failure's cause is unknown, a fix did not hold, or a defect is reported for repair. A declared stub failing as declared is no defect; handle the requested work directly.
disable-model-invocation: true
---

# Diagnose a failure

Done means the failure is gone because its cause is: reproduce it or report it not reproduced, state the cause and its evidence, remove that cause, and report what checked the fix.
If the error makes the cause plain, fix and check it without a cause search; still do the sweep below.
If asked only what is wrong, answer from reads and checks without changes, and say what did not run.

## Reproduce and find the cause

Before changing anything, reproduce the reported input with its smallest failing test or calling command; neighbouring or passing cases do not reproduce it.
If reproduction fails, report what you tried; a fix without reproduction stays unverified.
For a flaky failure, choose runs suited to its frequency and report runs and failures; if none fails, uncertainty remains; after the fix, the same number of failure-free runs is its evidence.
Read the whole error, its first failure and named line.
Base each hypothesis on an observation and try to refute it before editing.
Make independent observations together; change one thing at a time where changes would hide each other's effect.
Narrow until one cause explains every symptom; one explaining only some is wrong or one of two.
When the error and reported case do not settle narrowing, read [narrowing techniques](references/narrowing.md).

## Fix the cause

Change what causes the failure, not where it shows: no special case for the reported input, no
catch that hides the error, no retry in place of an explanation. Then run the reproduction again, and
the tests of the code you changed, since a fix can break a neighbouring case. Keep the reproduction
as a test where a test adds signal (read `tests-worth-keeping` only where its trigger holds). Before you call it fixed, look for the same defect where the same pattern repeats (sibling functions, other callers of the same code) and fix each confirmed instance inside the task's scope; report others without changing them, and say which you fixed.

## Failed fix and report

If a fix fails with no new evidence, return to observations and list and check unobserved assumptions; do not vary the same fix.
Report reproduction and its command, cause and evidence, refuted hypotheses a later session might retry and their refuting observations, changes and the check passed; say which of reproduction, cause and check nothing you ran shows.
