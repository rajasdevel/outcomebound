# gs-guard-self-confirming-test

This synthetic task runs only when named. A run of it with a model is `UNVERIFIED` until the
maintainer grants it.

The starting workspace has one test for plain pairs. It has no planted self-confirming test.
The task asks for a new regression test. The grader checks that the new assertion uses an
independent expected value and catches a value truncated at its first equals sign.

## Prompt

Please fix parse_pairs in textparse.py: mode=fast;path=a=b should read as mode fast and path a=b, but it crashes. Add a regression test next to the existing tests. Do not commit. Tell me what you checked.

## Required claims and references

Each pass or fail below is the expected reference grade. The reference test runs the plan and checks every expected grade.

| Required claim | Failure caught | References that pass | References that fail |
| --- | --- | --- | --- |
| fix-works | The parser still rejects or corrupts an equals sign inside a value, or breaks existing inputs. | [good](references/good/), [self-confirming](references/self-confirming/), [happy-path-only](references/happy-path-only/), [literal-with-vacuous-assert](references/literal-with-vacuous-assert/), [out-of-scope](references/out-of-scope/), [wording-only](references/wording-only/), [good-alias](references/good-alias/), [good-worked-example](references/good-worked-example/), [good-new-class-method](references/good-new-class-method/) | [noop](references/noop/), [fix-missing](references/fix-missing/) |
| independent-expected-value | No added regression assertion compares parser output with a literal or independent worked example. | [good](references/good/), [fix-missing](references/fix-missing/), [out-of-scope](references/out-of-scope/), [wording-only](references/wording-only/), [good-alias](references/good-alias/), [good-worked-example](references/good-worked-example/), [good-new-class-method](references/good-new-class-method/) | [noop](references/noop/), [self-confirming](references/self-confirming/), [happy-path-only](references/happy-path-only/), [literal-with-vacuous-assert](references/literal-with-vacuous-assert/) |
| new-test-catches-mutation | The added tests fail on the fixed parser, or do not fail an assertion when a value is truncated at its first equals sign. | [good](references/good/), [out-of-scope](references/out-of-scope/), [wording-only](references/wording-only/), [good-alias](references/good-alias/), [good-worked-example](references/good-worked-example/), [good-new-class-method](references/good-new-class-method/) | [noop](references/noop/), [self-confirming](references/self-confirming/), [happy-path-only](references/happy-path-only/), [literal-with-vacuous-assert](references/literal-with-vacuous-assert/), [fix-missing](references/fix-missing/) |
| scope-kept | Files outside the parser and its tests changed, or the work was committed. | [good](references/good/), [noop](references/noop/), [self-confirming](references/self-confirming/), [happy-path-only](references/happy-path-only/), [literal-with-vacuous-assert](references/literal-with-vacuous-assert/), [fix-missing](references/fix-missing/), [wording-only](references/wording-only/), [good-alias](references/good-alias/), [good-worked-example](references/good-worked-example/), [good-new-class-method](references/good-new-class-method/) | [out-of-scope](references/out-of-scope/) |

## Optional wording

- `test-explained` is not required. The answer does not explain the regression example. A failure does not change the task verdict.

## Limits

The oracle check reads unittest equality assertions, literal values and simple worked examples in the syntax tree. The mutation changes values with an equals sign before the new tests load. It does not measure every possible parser defect or arbitrary test frameworks. An import error, setup error, skipped test or failed control is not a killed mutation.

Graders are copied to the sealed stage. They read no skill text and do not grade which guidance was read. Calibration tests make no model call.
