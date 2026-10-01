---
name: tests-worth-keeping
description: Use when writing, changing or judging a test, or when the project's tests already fail before you begin. What makes a test worth keeping, when no new test is warranted, and what the report keeps apart.
---

# Tests worth keeping

A test is worth keeping when some change to the code it covers would make it fail. Which tests
to write, and when to run them, is yours; this is the bar a test you keep meets, and what your
report keeps apart.

## In a project that already fails

Before changing anything, run the tests relevant to the change and note which already fail and
why. Report new failures apart from those. A pre-existing failure is left as found unless fixing
it is the task: not skipped, not marked expected, not loosened until it passes.

## What a kept test shows

- **A break it catches.** Name the production change that would make it fail. If none would,
  the test cannot fail: an assertion that recomputes the expected value the way the code does, an
  assertion on what a test double was told to return, a value compared with itself. Where you
  doubt a test can fail, break the code and watch it; that settles the doubt, and is no step
  every test needs.
- **Observable behaviour.** Assert through the interface a caller uses, against an expected value
  the code did not produce: a known-good literal, a worked example, the spec. A test that pins how
  the code is written, such as the order of calls on collaborators, private state or the exact
  wording of a message that is not the contract, fails on a refactor that changes nothing
  observable. Rewrite it against the behaviour or drop it.
- **The same verdict every run**, alone and beside other tests. Control time, ordering, shared
  state, the network and randomness; a retry hides the cause.
- **For a bug, the reported case.** The input and the symptom the report names, not a
  neighbouring case that is easier to write. A test for a bug that passes before the fix does not
  reproduce it.

## When no new test is warranted

An existing test already fails on the break; the change is to generated files, configuration or
documentation, where a build, render or lint check catches the break; or the risk sits at a layer
a unit test does not reach, such as integration, delivery or rendering, where a runtime check is
the test. Say so in the report, in place of a test that adds nothing.

## Deleting a test that cannot fail

A test no production change would fail, or one that fails only on refactors, is deleted or
rewritten, and the change says what it caught before, if anything.

## The report

Failures that predate the work, apart from any the work caused; for each test added, the break it
catches; and what no check exercised, as `UNVERIFIED`.
