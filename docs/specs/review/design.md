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
| `WARN` is a line verdict beside PASS, FAIL and INFO. The verdict is PASS or FAIL, and there is no UNVERIFIED: `check` reads one file, so no evidence it needs is ever absent; `sweep` refuses a missing folder (`REVIEW_FOLDER_MISSING`, exit 1) and counts the files it did not read on its first line | an UNVERIFIED for a stale ref, which makes a warning stop a run | agent | assumed |
| A file with no finding passes, with an INFO line. A review may find nothing | failing, which makes a clean review impossible to record | agent | assumed |
| There is no severity scheme and no limit on findings | a severity column, which no check here uses; a cap chosen without evidence | agent | assumed |
| Exits as the other check verbs: 0 PASS; 1 FAIL or a refusal (`REVIEW_UNREADABLE`); 2 a usage error. Text and `--json` carry the same lines, each with what it does not establish and, for a FAIL, a `next:` step. Text that came from the file is printed with characters outside printable ASCII escaped | a new code for WARN | agent | assumed |
| `outcomebound review since FILE [--root DIR] [--json]` is a separate subcommand, so `check` and `sweep` stay free of Git. It reads the file's `Reviewed:` ref (the first such line outside a fence), has Git resolve it to a commit, and prints what differs between that commit and the work tree of the repository at `--root` (default `.`): each changed tracked path with its added and removed lines and its hunks, each untracked path Git does not ignore (as a new file, with no hunks), and, for each finding, the `path:line` or `path:line-line` references in its text that name a changed path. It reuses the `size` verb's read-only Git helpers, so it writes nothing and refreshes no index. Its result is a report or UNVERIFIED, never PASS or FAIL: with no `Reviewed:` line, a ref Git cannot resolve to a commit, a ref that starts with `-`, a root that is not a Git work tree, or a file it cannot read, it prints `UNVERIFIED` and the reason and exits 1. A report exits 0, also when nothing changed. The report's lines each end with what they do not establish: a changed path does not mean a finding is stale or fixed; an unchanged one does not mean it still holds; the ref is not shown to name what the reviewer read; paths Git ignores, and a rename's old content, are not compared; the references are read from the finding's prose, outside code fences, and a finding that names no `path:line` cites nothing. A cited line also reads `line changed` when it lies in a removed or replaced span of the reviewed file (a hunk's old side), which says the text there is gone, not that the finding is answered. The JSON report is `schemas/review-since.schema.json` | folding `since` into `check`, which would end the Git-free property; a verdict, which no evidence here supports; reading the diff of the reviewed ref to HEAD only, which misses uncommitted work; matching findings by prose or by title, which no check can do | agent | assumed |
| `outcomebound review sweep [DIR]` runs `check` on every review file of a work folder (default `.agents/work`): each `.md` file one to four levels below it that holds a `Reviewed:` line outside a fence, whatever its headings, so a review whose headings are malformed is read and fails rather than drops out. It enters no linked folder, reads no linked file and no file over 1 MB, counts each file it did not read on its first line and names them with `--verbose`. Its first line is the verdict and the counts; `--json` adds an optional `files` object to the same report. `make release-check` runs it on the main checkout's `.agents/work`, resolved from the Git common directory, so a release cut in a worktree reads the reviews other sessions left; CI does not, since a clone holds no `.agents`. A report with no `Reviewed:` line is not read: its issues reach a release only as milestone issues (field: a review another session left with open findings was not seen while pull requests merged and a release was drafted) | a ledger file of known issues, a second place to forget; a date filter, which hides an old open finding; selection by finding headings alone, which reads decision briefs as reviews; a walk of the whole folder, which on a working machine reads hundreds of thousands of files | agent | decided |

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

`tests/test_review_since.py`: a reviewed ref that is an ancestor, a branch and a tag; changed, renamed, deleted, binary and untracked paths; a hunk's ranges; a citation of a changed path, of an unchanged one, of a changed line, and in a fence; each UNVERIFIED reason; a work tree the verb leaves as it found it (Git status and index unchanged); the JSON report matches its schema.

`tests/test_review_check.py`: each FAIL code has a file that triggers it and the clean file beside
it; text between headings, fenced lines and deeper headings are data; a review with no finding
passes; `--at` warns and leaves the verdict; the JSON report matches its schema and carries the
text report's verdict; output escapes; an unreadable file is a refusal. The verb is listed in the
launcher's help tests. The format has not met a real review file: the release canary is the first
such run, and what it finds becomes a case in the suite.
