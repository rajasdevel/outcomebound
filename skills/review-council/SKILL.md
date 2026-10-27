---
name: review-council
description: Use when a second opinion from other models or harnesses is worth asking for, as for a design, a release candidate, or a change whose miss would reach users. Plans the run and waits for the person's yes before it runs.
---

# Review council

You are done when the person saw the plan and said yes before any reviewer ran, each reviewer
that answered has a review file, each reviewer that did not is named with its reason, and every
finding you kept has one disposition with the evidence for it.

## When it is worth asking

Every reviewer spends the person's credits, so ask whether a second reader would
change a decision. It would for a design that others will build on, for a release candidate, and
for a change that would hurt users if wrong and that no check you can run would catch. It would not
for a change a test or the project's gate already covers, a fix to text for people, or a doubt you
can settle by reading the code. A reader from another model family adds more than another run of
your own, so name reviewers that are not your model.

## Plan, and ask

Run `outcomebound review council --plan` with what to review (`--range A..B`, `--base REF`, or
`--file PATH` for a design or a spec), a lens (what the reviewers look at, one lens for a run so
that the answers compare), and a `--reviewer harness:model[:effort]` for each reviewer. With none
named, the reviewers are those of the project's or the person's council file, else the engine's
built-in default of one reviewer, and the plan says which. Those names are examples, so check them
against what the person's logins offer. Name more reviewers when the question needs them. The plan
runs nothing.

Show the person the plan as printed, so that their yes is to the argv, the timeout and the cap
and not to your summary of them. Then say in plain words who reviews, what they read, that it
spends their credits, any program the plan says is not found, which login each Claude reviewer bills, any reviewer the
plan marks as read-only not confirmed (one is run only if the person names it), and which
safeguards no run has shown. Then ask for a plain yes. Only that yes lets you run `--accept`. A yes to an earlier plan, or to reviews in
general, is not a yes to this plan: a changed reviewer, range, lens or cap is a new plan. A failed
reviewer you want to run again is a new plan too. If you get no yes, you stop at the plan. You
never start `codex`, `claude -p` or another reviewer by hand, because that skips the safeguards the
plan lists.

## Run

Run the same command with `--accept` in place of `--plan` and with `--plan-id` set to the id the plan
printed, in the background, and wait once for it
to end. It runs the reviewers in parallel, read-only, each on a snapshot of the reviewed revision.
A run that the plan id refuses differs from the plan the person approved, so plan again and ask
again. A reviewer that fails or times out is reported and the rest go on; do not read a missing file as a
clean review. Report to the person which reviewers answered, which did not and why, and the spend
the run printed, which is an estimate.

## Merge and dispose

Open each review file: the run prints each reviewer's verdict and finding count, and a verdict of
pass with a body that says the reviewer could not read the code is a failed review. Take the
findings with the `review-findings` skill. Where reviewers raise one cause, keep it once and note
who raised it; agreement is no proof and one reviewer's finding stands or falls on its evidence. A
`Citation check:` line under a finding is the engine's: a place the finding names is not in the
reviewed revision, is ambiguous, or the finding names none. It shows that the finding needs your
reading, and does not show it wrong. Write the dispositions into the review files and run
`outcomebound review check` on each. A reviewer reading again after your fix is a new plan.
