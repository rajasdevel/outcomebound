---
name: tests-worth-keeping
description: Use when changing money, date, limit or permission logic, when project tests fail before work, when skipping, loosening or deleting a test, or when a test's proof of behaviour is uncertain. For each test added or assessed, assert through the caller's interface an expected value that neither the code under test nor a copy of its algorithm produces (a literal, worked example or spec). Name the break each added or assessed test would catch. For a refusal test, reach the named refusal, not setup failure or an earlier guard.
disable-model-invocation: true
---

# Tests worth keeping

Keep a test only if a production change would make it fail; name that break for each test you add or keep.
For new deciding logic (a branch, parse, money or access), add one small test unless an existing test catches its break; changes without such logic need none.
Choose tests and timing except fixed hand-off tests; keep those as written and send requirement conflicts to the package's author.

## In a project that already fails

Where the tests may already fail (CI is red, the person says so, or a run before your change
showed it), note which fail and why before you change anything. Where a test fails after your
change for a reason the change may not explain, run it on the unchanged code before you treat it
as yours. The base is the one the outcome is judged against: the release in production where the
outcome is stability against that release, else the last revision where the behaviour worked;
compare under the same conditions. Report new
failures apart from those that were already there. A pre-existing failure is left as found unless fixing
it is the task: not skipped, not marked expected, not loosened until it passes. A test that fails
on one run and passes on the next, with the same inputs and conditions, is flaky: report it as
flaky with both results; a rerun that passes is not its verdict. Compare failures by their cause and
the behaviour they reached, not only by their names: a setup failure leaves the behaviour it
prevented unverified, and before another long run, fix the prerequisite the last output names. Before you rerun a claim of a validation plan,
`outcomebound validation status <plan>` reads its last kept result and says whether a path the
claim declares has changed since (`CURRENT`, `CHANGED` or `UNVERIFIED`); it runs nothing, and
`CURRENT` is not a pass.

## What a kept test shows

If no production change would fail a test, delete or rewrite it and say what it caught before, if anything.
If in doubt, break the code and watch the test fail; this is not required for every test.
For a refusal or deliberate break, reach the named behaviour, not setup failure or an earlier guard.
Assert observable behaviour through the caller's interface against a known-good literal, worked example or spec, never the code's result or a copy of its algorithm.
Rewrite or drop tests that pin implementation without an observable change.
If examples would settle doubt, read [examples](references/examples.md).
For a routinely restamped snapshot or golden file, name the unwanted behaviour it detects and whether another check covers it.
Keep verdicts stable alone and beside other tests; retries hide causes.
For a bug, test the reported case as `diagnose` reproduces it.

## Coverage and report

When an existing test catches the break, a build, render or lint check catches a generated-file, configuration or documentation change, or the risk needs a runtime integration, delivery or rendering check, say which in the report instead of adding a redundant test.
For each completion-bar check or material claim no check exercised, report it as unverified, with the missing evidence and what would settle it.
