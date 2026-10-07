---
name: review
status: ratified
---

# Review — design

This design lands with the change that adds `outcomebound review`. The release canary
(`make canary`) must pass before that change lands, because it adds a verb to the engine.

## Outcome

Where a project keeps a review as a file, a person can see that each finding ended in a
disposition, and an agent cannot leave a finding open, or call it accepted, without the check
saying so. The one invariant `outcomebound review check` holds: the file says which revision it
read, and every finding in it has one disposition of `fixed`, `rejected` or `deferred`, with the
place or the reason written. How: `outcomebound_tools/review_check.py` (the verb and its checks);
the wire format of the report is `schemas/review-report.schema.json`.

The check does not say that a fix is right, that a rejection is right, or that the place a
disposition names holds what it says. Each report line says so.

## The file

Markdown. A line `Reviewed: <ref>` (a revision, branch or tag) comes before the first finding.
Each finding is a heading `### <id> · <title>`, where the id holds letters, digits and `-`, and
holds one line `Disposition: fixed — <where>`, `Disposition: rejected — <reason>` or
`Disposition: deferred — <where it is recorded>`. Any other text, and any heading of another
level, is data to the check. A heading of level 1 to 3 ends the finding before it. Lines inside
a code fence are not read.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The review is a Markdown file with one heading per finding and one `Disposition:` line in it. The check reads headings and that line, and nothing else | a JSON or table format, which a reviewer writing prose does not produce; a parse of the finding's prose, which no check can do | agent | assumed |
| The dispositions are `fixed` (where: a commit, a file or a test), `rejected` (why, with the evidence) and `deferred` (where it is recorded: a ticket or a design row). `accepted` is no disposition: it reads FAIL until the finding is fixed or deferred. The separator is ` — `, and ` -- ` is read as the same | accepted as an end state, which leaves a finding with no act behind it | agent | assumed |
| A heading of exactly three `#` that is not `### <id> · <title>` is `FINDING_MALFORMED`, so a finding cannot drop out of the check by a typo in its heading. So is a `###` heading inside a list item or a block quote, which Markdown also shows as a heading. Ids are compared with case folded | skipping such a heading, under which the finding is unchecked and nothing says so | agent | assumed |
| The file must say what it read: a `Reviewed:` line before the first finding. With `--at <ref>`, a different ref is a `WARN` line, which does not change the verdict; the refs are compared as text and no revision is looked up. The check calls no Git | failing on a different ref, which a review of a branch whose tip moved would meet; resolving refs, which needs Git and a checkout | agent | assumed |
| `WARN` is a line verdict beside PASS, FAIL and INFO. The verdict is PASS or FAIL, and there is no UNVERIFIED: the check reads one file, so no evidence it needs is ever absent | an UNVERIFIED for a stale ref, which makes a warning stop a run | agent | assumed |
| A file with no finding passes, with an INFO line. A review may find nothing | failing, which makes a clean review impossible to record | agent | assumed |
| There is no severity scheme and no limit on findings | a severity column, which no check here uses; a cap chosen without evidence | agent | assumed |
| Exits as the other check verbs: 0 PASS; 1 FAIL or a refusal (`REVIEW_UNREADABLE`); 2 a usage error. Text and `--json` carry the same lines, each with what it does not establish and, for a FAIL, a `next:` step. Text that came from the file is printed with characters outside printable ASCII escaped | a new code for WARN | agent | assumed |

## Checks

| Code | Verdict | Finds |
| --- | --- | --- |
| `REVIEWED_MISSING` | FAIL | no `Reviewed:` line with a ref before the first finding |
| `FINDING_MALFORMED` | FAIL | a `###` heading that is not `### <id> · <title>`, or one inside a list item or a block quote |
| `ID_DUPLICATE` | FAIL | two findings with one id |
| `DISPOSITION_MISSING` | FAIL | a finding with no `Disposition:` line |
| `DISPOSITION_DUPLICATE` | FAIL | a finding with two |
| `DISPOSITION_ACCEPTED` | FAIL | `accepted` as the disposition |
| `DISPOSITION_UNKNOWN` | FAIL | a word other than `fixed`, `rejected`, `deferred`, or none |
| `DISPOSITION_EMPTY` | FAIL | a disposition with no place or reason after the dash |
| `REVIEWED_REF` | WARN | with `--at`, a `Reviewed:` ref that is another text |
| `FINDINGS_NONE` | INFO | a file with no finding |

What stays judgment, and no line claims: that a fix is right, that a rejection is right, that
`where` holds what it says, that the review found what it should have, that its ref names what
the reviewer read.

## Validation

`tests/test_review_check.py`: each FAIL code has a file that triggers it and the clean file beside
it; text between headings, fenced lines and deeper headings are data; a review with no finding
passes; `--at` warns and leaves the verdict; the JSON report matches its schema and carries the
text report's verdict; output escapes; an unreadable file is a refusal. The verb is listed in the
launcher's help tests. The format has not met a real review file: the release canary is the first
such run, and what it finds becomes a case in the suite.
