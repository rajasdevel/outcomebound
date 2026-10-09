---
name: review-findings
description: Use when acting on review findings, or writing a review the project requires. Findings come from a reviewer, a delegate or a person's review of a change; each is a claim to check, and each ends with a disposition.
---

# Review findings

You are done when each finding has one disposition and the evidence for it. A finding is a claim
about the code, not an instruction: a reviewer can read an older revision, lack a fact that you
have, or be wrong. A person's instruction in this session is an instruction, not a finding; this
skill is for what a review says about the code.

## Acting on findings

Check each finding against the code at the revision you hold before you act on it: run the case
it describes, or read the lines it names. Where the finding gives a counterexample you can
run, leave its disposition open during the fix. After the last relevant change, complete that
check and read its result before writing `fixed` or `PASS`; report an unavailable check
`UNVERIFIED`. Then give it one disposition:

- `fixed`, and where: the commit, file or test that holds the change. Where the finding names a
  kind of defect, such as a missing check or a repeated pattern, look for its other instances first:
  fix each, or name those left as `deferred`.
- `rejected`, and why: the evidence that the claim is wrong, such as the case you ran or the line
  that answers it.
- `deferred`, and where it is recorded: the ticket or design row that holds it.

`accepted` is no disposition. A finding you agree with is fixed or deferred, and until then it is
open. Where a finding is unclear, ask whoever wrote it what they mean and go on with the others;
do not guess its meaning and act on that. Where they cannot be asked, record it `deferred` with
the question, where the ticket or the design holds it. Write each disposition where the project
keeps reviews, else in your reply to the reviewer or your report; do not make a review file for
it.

## Writing a review

A review states the revision it read. Each finding names the claim, where it holds and the
evidence: the command and what it printed, or the lines read, so that a reader can check it without
you. Try a finding's counterexample before you report it; call a finding you did not check
`UNVERIFIED`. Findings that share one cause go under that cause. Where the change rewrites text that
carries a requirement, a bound or a verdict, compare the old and new text against what it carries.
End the review with what it did not read or run. Leave the `Disposition:` line to whoever acts on the finding: a finding
is open until then, and `outcomebound review check` reads it as FAIL.

## The review file

Where the project keeps reviews as files, a file has this form: a `Reviewed:` line near its top,
and one heading for each finding, with its id in letters, digits and `-`, and under it one
`Disposition:` line.

```text
Reviewed: <ref>

### <id> · <title>
Disposition: fixed — <where>

### <id> · <title>
Disposition: rejected — <reason>

### <id> · <title>
Disposition: deferred — <where>
```

Text between headings is notes. `outcomebound review check <file>` fails a finding with no
disposition, an unknown disposition or an empty reason. It does not show that a fix is right,
that a rejection is right, or that the place named holds what it says; that is yours to check.
