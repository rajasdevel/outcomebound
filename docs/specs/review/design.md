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
| `outcomebound review since FILE [--since REF] [--root DIR] [--json]` is a separate subcommand, in its own module, so `check` and `sweep` stay free of Git. The ref is `--since REF` where given, else the file's `Reviewed:` line, the one `check` reads (before the first finding; a later one is not read, and `--since` names it). Git resolves the ref to a commit (`rev-parse --verify <ref>^{commit}`, the ref one argument, a ref starting with `-` refused). `--root` is any folder inside a Git work tree (default `.`); paths are relative to its top level, as a review cites them. The verb prints what differs between that commit and the work tree: each changed tracked path with its status (modified, added, deleted, renamed with its old path, type-changed), added and removed lines and hunks, read from `diff-index --raw -z -M` and `diff-index -p --unified=0 -M --no-ext-diff --no-textconv`, with Git's optional locks off; and each untracked regular file Git does not ignore, as a new file with no hunks (a non-regular entry is counted on one line, not listed). A hunk holds its old and new start and count, a count of 1 being the one Git leaves out of the header, and a count of 0 being a span with no line. For each finding it reads the references in its text outside code fences (inline code is read): a path, then optionally `:N`, `:N-M` or a comma list of those, the path holding a `/` or a dotted suffix and not following `://`. A reference names a changed path when it equals one, else when it is a whole-component suffix of exactly one (`a/b.py` of `x/a/b.py`); a suffix of several is shown as ambiguous with its candidates and counts as a citation of each. A path cited with no line counts. A cited line reads `line changed` when it lies in a span the reviewed file lost (a hunk's old side with a count above 0; every line of a deleted file). Its result is a report or UNVERIFIED, never PASS or FAIL. UNVERIFIED, with the reason on the first line and exit 1: no ref in the file and none given, a ref Git does not resolve to a commit (with Git's own message), a root that is no Git work tree, an unreadable file. A report exits 0, also when nothing changed. When the resolved ref is a branch, a remote branch or `HEAD`, the report says its tip now may not be what the review read; `--since` is the cure. The text report prints the ref, the first 12 characters of the commit, the changed paths, the hunks of cited paths only (all under `--verbose`), each finding that cites a changed path, and one block of what it does not establish: a changed path does not mean a finding is stale or fixed, and an unchanged one does not mean it still holds; the ref is not shown to name what the reviewer read; ignored paths are not compared; a finding that names no path cites nothing, and text under a malformed finding heading is read by no finding; a reference is read from prose, so a path named another way is missed. The JSON report is `schemas/review-since.schema.json` | folding `since` into `check`, which would end the Git-free property; a verdict, which no evidence here supports; a diff of the reviewed ref to HEAD only, which misses uncommitted work; matching findings by prose or title; default Git context, which marks unchanged lines near an edit as changed | agent | assumed |
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

`tests/test_review_since.py`: a reviewed ref that is an ancestor, a branch, a tag, an abbreviated hash and one with spaces; `--since` over the file's line; a root that is a subfolder; changed, renamed, deleted, binary, untracked and non-regular paths; hunks, including a count of 1 and of 0; a citation of a changed path, of an unchanged one, with no line, as a suffix (unique and ambiguous), in inline code, in a fence, after `://`, and of a changed and an unchanged line near each other; a rename's old path; two `Reviewed:` lines; each UNVERIFIED reason; a work tree the verb leaves as it found it (Git status and index unchanged); the JSON report matches its schema.

`tests/test_review_check.py`: each FAIL code has a file that triggers it and the clean file beside
it; text between headings, fenced lines and deeper headings are data; a review with no finding
passes; `--at` warns and leaves the verdict; the JSON report matches its schema and carries the
text report's verdict; output escapes; an unreadable file is a refusal. The verb is listed in the
launcher's help tests. The format has not met a real review file: the release canary is the first
such run, and what it finds becomes a case in the suite.
