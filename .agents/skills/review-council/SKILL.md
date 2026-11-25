---
name: review-council
description: Use when a second opinion from other models or harnesses is worthwhile (a design, release candidate or change whose miss would reach users). Plan first; run only after the person's yes.
disable-model-invocation: true
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
your own, so name reviewers that are not your model. Run a council when the person names one, or
once at a major milestone or decision; never in a loop.

## Plan, and ask

Run `outcomebound review council --plan` with what to review (`--range A..B`, `--base REF`, or
`--file PATH` for a design or a spec), a lens (what the reviewers look at, one lens for a run so
that the answers compare), and the reviewers: `--council NAME` for a council the person named in
the `.outcomebound/council.json` of their home folder (`--defaults` lists them), or a
`--reviewer harness:model[:effort]` for each. With neither, the reviewers are those of the council file, else the engine's built-in
default of one reviewer, and the plan says which. Those names are examples, so check them against
what the person's logins offer. The plan runs nothing.

Show the person the plan as printed, so that their yes is to the argv, the timeout and the cap
and not to your summary of them. Then say in plain words who reviews, what they read, that it
spends their credits, any program the plan says is not found, each reviewer's account folder and
the keys set (what decides the account it bills), any reviewer the plan marks as read-only not confirmed (one is run only if the person names it), and which
safeguards no run has shown. Then ask for a plain yes. Only that yes lets you run `--accept`. A yes to an earlier plan, or to reviews in
general, is not a yes to this plan: a changed reviewer, range, lens or cap is a new plan. A failed
reviewer you want to run again is a new plan too. If you get no yes, you stop at the plan. Outside
the host path below, you never start `codex`, `claude -p` or another reviewer by hand, because that
skips the safeguards the plan lists.

## Run

Run the same command with `--accept` in place of `--plan` and with `--plan-id` set to the id the plan
printed, in the background, and wait once for it
to end. It runs the reviewers in parallel, read-only, each on a snapshot of the reviewed revision.
A run that the plan id refuses differs from the plan the person approved, so plan again and ask
again. A reviewer that fails or times out is reported and the rest go on; do not read a missing file as a
clean review. Report to the person which reviewers answered, which did not and why, and the spend
the run printed, which is an estimate.

## On a host that starts agents itself

Where the person names a council and the host starts its own agents (T3 Code), you may run it as
host threads instead. The council must be in the `.outcomebound/council.json` of the person's home
folder first; a council named only elsewhere is not one the host route runs.

1. Run `outcomebound review council --defaults --council NAME --host`, with any lens, timeout or
   spend-cap option. It prints each seat, resolved as the plan resolves it, or marked "host only"
   where the engine cannot start it, with its model and effort as written; the lens, timeout and
   cap that apply; and the answer form. Where it refuses, show the person the refusal and start no
   thread.
2. Resolve the revision to a commit (`git rev-parse --verify REV^{commit}`), and use that commit,
   not a branch name, from here on.
3. Before you ask for the yes, show the person: the commit; the range or the files; the lens; for
   each seat, the exact host provider instance that will run it and its billing mode where you
   know it (else say it is not known); the timeout and cap asked for; and which of these controls
   the host enforces: on host threads, none. No spend cap, timeout or read-only mode holds except
   by the brief, and no snapshot hides the revision's instruction files: the run is "read-only by
   brief, not enforced". Where the person asked for subscription use only, a seat runs only on an
   instance you checked bills their subscription. Start no thread without a plain yes to this.
4. Start one thread for each seat, on exactly the instance you showed, with the seat's model and
   effort. Each brief names the commit, the range or the files, and the lens; says that the
   reviewer reads and changes nothing; gives the answer form the listing printed, with the seat's
   tag; and names the one answer file it writes, `TAG.answer` in
   `.agents/work/council/<first 12 characters of the commit>/` of the main checkout.
5. File each answer with `outcomebound review council --file-answer FILE --revision COMMIT --seat
   "TAG SEAT" --out FOLDER/TAG-host.md`, where FOLDER is that folder. It files an answer only in the
   answer form: a first line of `Verdict: FAIL`, `Verdict: UNVERIFIED` or `Verdict: PASS`, and for
   a `FAIL` at least one finding heading `### TAG-N · title`. It removes the `Disposition:` and
   `Reviewed:` lines the reviewer wrote outside code fences, and puts the engine's `Reviewed:` line
   first. A refused answer stays where it is, outside the review record: report that seat to the
   person as a failed review, by name. On host threads no citation was checked.

## Merge and dispose

Open each review file: the run prints each reviewer's verdict and finding count, and a verdict of
pass with a body that says the reviewer could not read the code is a failed review. Take the
findings with the `review-findings` skill. Where reviewers raise one cause, keep it once and note
who raised it; agreement is no proof and one reviewer's finding stands or falls on its evidence. A
`Citation check:` line under a finding is the engine's (an engine run's only; on host threads no
citation was checked): a place the finding names is not in the
reviewed revision, is ambiguous, or the finding names none. It shows that the finding needs your
reading, and does not show it wrong. Write the dispositions into the review files and run
`outcomebound review check` on each. A reviewer reading again after your fix is a new plan.
