# Testing guidance research trials

Status: candidate comparison for the 1.6.0 development branch. No candidate is installed by
OutcomeBound until its evidence and review support it. The release version stays unchanged
until release preparation.

## Question and sources

Does a small addition to `tests-worth-keeping` improve security-fix validation or property
selection beyond the existing skill, without adding work to an ordinary fix?

The mechanisms come from the public [Trail of Bits skills](https://github.com/trailofbits/skills)
at commit `82fe8226252622fa807643bdca1710901198553a`: post-patch-validation 0.2.2 and
property-based-testing 1.2.2. The source files and licence were read on 2026-10-09. The candidate
uses original wording; no upstream program or skill text is imported. Source inspection does
not establish a benefit from the candidate.

The existing skill already rejects tautological tests and failures that do not reach the
behavior under test. The comparison concerns only a distinct regression variant, a benign
control, and selecting useful properties. It does not add a security procedure to every fix.

## Cases

| Fixture | Outcome measured | Control |
| --- | --- | --- |
| `patch-validation` | Assess synthetic fixes and supply a regression that separates a complete fix from the original and incomplete fixes | A setup failure cannot establish a security assertion; valid input must keep working |
| `property-oracles` | Keep tests that distinguish the specified behavior from seeded defects | Vacuous or self-confirming tests do not count as evidence |
| `testing-no-work` | Complete an ordinary bounded fix with the existing adequate test | No extra test system, review procedure or planning files |

These cases run only when named. They do not expand the default fixture batch. Deterministic
self-checks must accept seeded correct artifacts and reject seeded defective artifacts before
a model runs. They establish that the grader can distinguish those seeds, not that it catches
every wrong answer. Review meaning and command evidence separately.

## Fixed comparison

Use the existing runner and the same fixtures for both configurations. The baseline is the
current 1.5.0 skill text; the candidate changes only `tests-worth-keeping` and a narrow reference
if the trial needs one. Both use the current kernel and other installed skills. Record source
commits and installed-file digests; the candidate skill digest is an intended difference.
Do not compare either configuration with the `none` arm as a substitute for this comparison.

The initial bound is 18 calls: three fixtures, two configurations and three repetitions. Use
`gpt-6.1-sol`, medium effort, and the ChatGPT-authenticated Codex CLI. Start one retained case
to check evidence collection, within this bound. No API-key fallback or automatic retry is
allowed. A call error or unsupported evidence path stops the campaign for diagnosis. Report
unused cells as UNVERIFIED. Do not increase the bound to obtain a preferred result. Run the target-case baselines first.
If both target cases pass in all three baseline repetitions, stop for saturation without
candidate calls: this comparison cannot show the required improvement. Unrun cells stay
UNVERIFIED. This stopping rule is fixed before the first call.

Codex CLI 0.160.1 does not expose observed model and working directory in its JSON stream.
Use the documented single-case native-retention mode and review its matched native record.
Keep the automatic failure or UNVERIFIED result intact. Requested model arguments, successful
retention and an answer that says PASS are not proof of model identity or task success.

## Candidate wording fixed before calls

If comparison reaches the candidate configuration, insert these two bullets after the current
reported-case bullet in `tests-worth-keeping`. All other skill text stays the same. This is an
experiment definition, not installed guidance:

> - **For a security repair**, a benign control checks that valid use still works. Compare the
>   reported exploit on prior and repaired code. If the repair may block only one input shape,
>   a small variant with the same root cause can distinguish the repair from a narrow filter.
> - **For a codec or normalizer**, a nontrivial roundtrip or idempotence check can cover a useful
>   property. Keep an independent expected representation beside a roundtrip: both directions
>   can make the same wrong change and still agree. Use valid inputs that exercise the property;
>   an empty loop proves nothing. This does not require a new library or random generator.

Both bullets are installed only in the candidate comparison copy. Score their two target
behaviors separately. A gain on one target does not justify the other bullet. If the combined
candidate does not meet the predeclared acceptance bar, neither bullet is installed.

## Decision before results

For each case and configuration, record actual task outcomes, missed defects, false findings,
extra workflow steps, available token use and elapsed time. Missing cost evidence stays
UNVERIFIED. Check the model identity, actual inputs, protected graders, output artifacts and
material command order. All trial data is synthetic. Publish configuration and redacted
results; keep raw native records out of the repository.

A 0/3 to 3/3 change in a target behavior is a signal to inspect, not a general reliability
estimate. The candidate must preserve all valid baseline outcomes and the no-work control.
Any material authority regression prevents integration. A smaller difference, missing
evidence or a saturated baseline is inconclusive: leave the candidate out of the installed
skill and retain the fixture for later use. Do not rewrite the case after results and count
a rerun as the original experiment.

Instruction changes that qualify still need the repository's required review and landing
checks. The two skill ideas are evaluated separately; a gain from one is not evidence for
the other. Version-matched external tool instructions remain a research-only candidate until
a concrete version-drift case shows a gap in the existing loading design.

## Recorded outcome

The initial campaign stopped after one baseline trial exposed an invalid complete-fix oracle
and an undeclared test replay interface. No candidate or retry ran. The
[E22 record](../docs/evaluations.md#e22-testing-guidance-research-trial-and-instrument-correction)
preserves the original result, separate native review and instrument corrections. The current
fixtures are for a fresh comparison; they do not retroactively qualify that trial. Candidate
benefit remains UNVERIFIED and installed skill text stays unchanged.
