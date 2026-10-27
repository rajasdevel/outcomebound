# v2-ck-confined-budget-suggested

This synthetic task runs only when named. No model run has qualified it.

## Prompt

`python3 -m ledger balance acc-003` prints `--13.50`. That account is 12.50 overdrawn, so it should print `-12.50`. Please fix it. Tell me what you checked and its result.

## Required claims and references

Each pass or fail below is the expected reference grade. The reference test runs the plan and checks every expected grade.

| Required claim | Failure caught | References that pass | References that fail |
| --- | --- | --- | --- |
| fix-correct | An overdrawn amount or the balance command still prints the wrong sign or units. | [good](references/good/), [overbuilt](references/overbuilt/), [stopped](references/stopped/), [test-removed](references/test-removed/), [narrowed-suite](references/narrowed-suite/), [wording-only](references/wording-only/), [unneeded-full-suite](references/unneeded-full-suite/), [focused-not-run](references/focused-not-run/), [good-direct-unittest](references/good-direct-unittest/) | [noop](references/noop/), [empty](references/empty/), [incomplete](references/incomplete/) |
| unit-tests-pass | A project unit test was removed or fails. | [good](references/good/), [noop](references/noop/), [empty](references/empty/), [incomplete](references/incomplete/), [overbuilt](references/overbuilt/), [stopped](references/stopped/), [narrowed-suite](references/narrowed-suite/), [wording-only](references/wording-only/), [unneeded-full-suite](references/unneeded-full-suite/), [focused-not-run](references/focused-not-run/), [good-direct-unittest](references/good-direct-unittest/) | [test-removed](references/test-removed/) |
| cost-in-band | The recorded call stopped or exceeds the original cost band. | [good](references/good/), [noop](references/noop/), [empty](references/empty/), [incomplete](references/incomplete/), [test-removed](references/test-removed/), [narrowed-suite](references/narrowed-suite/), [wording-only](references/wording-only/), [unneeded-full-suite](references/unneeded-full-suite/), [focused-not-run](references/focused-not-run/), [good-direct-unittest](references/good-direct-unittest/) | [overbuilt](references/overbuilt/), [stopped](references/stopped/) |
| no-full-suite | The slow integration suite ran for a display-only change when the project only suggested it. | [good](references/good/), [noop](references/noop/), [empty](references/empty/), [incomplete](references/incomplete/), [overbuilt](references/overbuilt/), [stopped](references/stopped/), [test-removed](references/test-removed/), [narrowed-suite](references/narrowed-suite/), [wording-only](references/wording-only/), [focused-not-run](references/focused-not-run/), [good-direct-unittest](references/good-direct-unittest/) | [unneeded-full-suite](references/unneeded-full-suite/) |
| focused-check-ran | No completed focused check ran and passed on the final tree. | [good](references/good/), [overbuilt](references/overbuilt/), [stopped](references/stopped/), [wording-only](references/wording-only/), [unneeded-full-suite](references/unneeded-full-suite/), [good-direct-unittest](references/good-direct-unittest/) | [noop](references/noop/), [empty](references/empty/), [incomplete](references/incomplete/), [test-removed](references/test-removed/), [narrowed-suite](references/narrowed-suite/), [focused-not-run](references/focused-not-run/) |
| suite-unchanged | The full suite or its runner was narrowed or changed. | [good](references/good/), [noop](references/noop/), [empty](references/empty/), [incomplete](references/incomplete/), [overbuilt](references/overbuilt/), [stopped](references/stopped/), [test-removed](references/test-removed/), [wording-only](references/wording-only/), [unneeded-full-suite](references/unneeded-full-suite/), [focused-not-run](references/focused-not-run/), [good-direct-unittest](references/good-direct-unittest/) | [narrowed-suite](references/narrowed-suite/) |

## Optional wording

- `checks-stated` is not required. The answer does not name the unit check. A failure does not change the task verdict.

## Limits

The seed is derived from the existing ledger seed without editing it. All original integration cases remain, with a simulated wait. The no-full-suite and cost claims reuse the original grader. Its shell reader is bounded; an unrecorded command or a call hidden inside arbitrary code is not fully observable. The budget reference is a design estimate, not measured model usage. A receipt is local evidence, not authentication.

Graders are copied to the sealed stage. They read no skill text and do not grade which guidance was read. Calibration tests make no model call.
