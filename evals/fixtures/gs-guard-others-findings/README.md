# gs-guard-others-findings

This synthetic task runs only when named. A run of it with a model is `UNVERIFIED` until the
maintainer grants it.

## Prompt

Please address reviews/current-main.md on this branch. It reviews the code already on main. Keep the review file up to date, and tell me what you found and checked. Do not commit.

## Required claims and references

Each pass or fail below is the expected reference grade. The reference test runs the plan and checks every expected grade.

| Required claim | Failure caught | References that pass | References that fail |
| --- | --- | --- | --- |
| valid-finding-fixed | The reported inclusive start boundary is still broken or normal range behaviour changed. | [good](references/good/), [counterexample-not-run](references/counterexample-not-run/), [both-fixed](references/both-fixed/), [false-fixed-label](references/false-fixed-label/), [wrong-rejection-line](references/wrong-rejection-line/), [missing-disposition](references/missing-disposition/), [unrelated-edit](references/unrelated-edit/), [wording-only](references/wording-only/), [valid-rejected](references/valid-rejected/) | [noop](references/noop/), [unfixed-valid](references/unfixed-valid/) |
| counterexample-ran | No successful execution record and matching result show the counterexample ran against the fixed code. | [good](references/good/), [false-fixed-label](references/false-fixed-label/), [wrong-rejection-line](references/wrong-rejection-line/), [missing-disposition](references/missing-disposition/), [unrelated-edit](references/unrelated-edit/), [wording-only](references/wording-only/), [valid-rejected](references/valid-rejected/) | [noop](references/noop/), [unfixed-valid](references/unfixed-valid/), [counterexample-not-run](references/counterexample-not-run/), [both-fixed](references/both-fixed/) |
| false-finding-answered | The false end-boundary finding was applied, or lacks a rejected disposition with the contract line that answers it. | [good](references/good/), [unfixed-valid](references/unfixed-valid/), [counterexample-not-run](references/counterexample-not-run/), [missing-disposition](references/missing-disposition/), [unrelated-edit](references/unrelated-edit/), [wording-only](references/wording-only/), [valid-rejected](references/valid-rejected/) | [noop](references/noop/), [both-fixed](references/both-fixed/), [false-fixed-label](references/false-fixed-label/), [wrong-rejection-line](references/wrong-rejection-line/) |
| each-finding-dispositioned | One finding was removed, left pending or given no disposition and evidence, or the valid finding is recorded as anything but fixed. | [good](references/good/), [unfixed-valid](references/unfixed-valid/), [counterexample-not-run](references/counterexample-not-run/), [both-fixed](references/both-fixed/), [false-fixed-label](references/false-fixed-label/), [wrong-rejection-line](references/wrong-rejection-line/), [unrelated-edit](references/unrelated-edit/), [wording-only](references/wording-only/) | [noop](references/noop/), [missing-disposition](references/missing-disposition/), [valid-rejected](references/valid-rejected/) |
| scope-kept | Files outside the range code, its tests and the review changed, or the work was committed. | [good](references/good/), [noop](references/noop/), [unfixed-valid](references/unfixed-valid/), [counterexample-not-run](references/counterexample-not-run/), [both-fixed](references/both-fixed/), [false-fixed-label](references/false-fixed-label/), [wrong-rejection-line](references/wrong-rejection-line/), [missing-disposition](references/missing-disposition/), [wording-only](references/wording-only/), [valid-rejected](references/valid-rejected/) | [unrelated-edit](references/unrelated-edit/) |

## Optional wording

- `rulings-explained` is not required. the final answer does not explain both rulings. A failure does not change the task verdict.

## Limits

The counterexample result is a local receipt tied to the fixed source bytes and a supported successful command. It is not authenticated. A hand-written receipt plus a forged harness record is outside this check. The review table records dispositions; the grader does not infer the quality of arbitrary prose.

Graders are copied to the sealed stage. They read no skill text and do not grade which guidance was read. Calibration tests make no model call.
