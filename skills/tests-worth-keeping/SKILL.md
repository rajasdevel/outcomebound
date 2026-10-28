---
name: tests-worth-keeping
description: Use when logic that decides money, dates, limits or permissions changes, when the project's tests already fail before you begin, when you skip, loosen or delete a test, or when it is uncertain whether a test proves the behaviour it claims. A test you add or assess asserts, through the interface a caller uses, an expected value that neither the code under test nor a copy of its algorithm produced (a literal, a worked example, the spec), names the break that would make it fail, and, for a refusal, reaches the refusal it names rather than failing at setup or an earlier guard.
---

# Tests worth keeping

Keep a test only if a production change would make it fail. New deciding logic (a branch, parse,
money or access) leaves one small test unless an existing test catches its break; a change
without such logic needs none. Choose the tests and their timing, except fixed hand-off tests:
keep those as written; send a conflict with a requirement back to the package's author.

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

- **The break caught.** Name the production change that would make it fail. If none would,
  delete or rewrite it and say what it caught before, if anything. If in doubt, break the code
  and watch it fail; this is not required for every test. A refusal or deliberate break must
  reach the behaviour it names, not fail at setup or an earlier guard.
- **Observable behaviour.** Assert through the caller's interface against an independent
  expected value: a known-good literal, a worked example or the spec, never the code's result
  or a copy of its algorithm. Rewrite or drop tests that pin implementation without an
  observable change. If examples would settle a doubt, read [the examples](references/examples.md).
- **A snapshot worth keeping.** For a routinely restamped snapshot or golden file, name the
  unwanted behaviour it detects and whether another check covers it.
- **A stable verdict**, alone and beside other tests. A retry hides the cause.
- **For a bug, the reported case**, as `diagnose` reproduces it.

## When no new test is warranted

An existing test catches the break; a build, render or lint check catches a generated-file,
configuration or documentation change; or the risk needs an integration, delivery or rendering
check at runtime. Say which in the report instead of adding a test that proves nothing more.

## The report

Separate failures that predate the work from failures it caused. For each added test, name its
break. Report each completion-bar check or material claim no check exercised as unverified,
with the missing evidence and what would settle it.
