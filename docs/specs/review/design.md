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

## The council

`outcomebound review council (--plan | --accept)` asks reviewers of other harnesses and models
for one independent, read-only review of a change, and writes one review file for each reviewer
that answers. How: `outcomebound_tools/review_council.py`; the flags of each harness are data in
`adapters/council.json`. The verb does not judge or merge: the session's agent reads each finding
against the code and disposes of it with the `review-findings` skill, and the `review-council` skill
tells it when a council is worth its cost and that the person must say yes first.

The request: what to review (`--range A..B`, or `--base REF` for `REF...HEAD`, or `--file PATH`,
repeated, for a design or a spec; a diff and files can go together), a lens (`--lens TEXT` or
`--lens-file FILE`), and the reviewers as `--reviewer harness:model[:effort]`, repeated. A missing
model or effort is that of the harness's first entry in the table's default council. The
reviewers come from `--reviewer` where it is given; else from the council file (below); else from
the built-in default council, which is one reviewer, and the plan prints which of the three it
used. A harness with no entry in the default council needs its model named, and a harness whose effort is part of its model id (Cursor,
OpenCode) takes no effort part. The reviewed revision is the end of the range, else `HEAD`.
`--timeout` (per reviewer, default from the table), `--budget-usd` (a spend cap for Claude
reviewers, given only where the person sets one), `--out` and `--root` complete it.

The council file is optional JSON that `schemas/council-config.schema.json` describes: `version` 1,
`reviewers` (a list of `harness:model[:effort]`), and optionally `lens`, `timeout_seconds` and
`budget_usd`. The verb reads the project's `.outcomebound/council.json` (committed) first, and where
that does not exist, the `.outcomebound/council.json` in the person's home folder; the first file found is read
alone and the other is not merged with it. A value given on the command line wins for that run. A
file that does not validate is a refusal that names it and the problem. The `adopt-outcomebound`
skill asks the adopter once which reviewers they want and writes the project's file only if they
name others.

`--plan` prints, and runs nothing and writes nothing: the sentence that the run spends the person's
credits; each reviewer with the program it would start, its exact argv (for a harness that takes the prompt as an argument, the last argument is the text
of the prompt file, which the plan names and does not print), its working folder, its
timeout, its answer and review files, its cost note; each flag that is a read-only safeguard with
the day it was read, where, and whether a run showed it (`UNVERIFIED` unless the table says
`tested`); a line for what no run has shown; and a plan id, a digest of the revision, the lens and
each reviewer's argv, environment and timeout. `--accept`, with the same arguments and
`--plan-id` set to that id, builds the argv, refuses a run whose id differs (for one, where
`ANTHROPIC_API_KEY` was set or unset after the plan and so changed Claude's login and flags), makes
the snapshot, and runs every reviewer in parallel. The person's yes is given to
the plan, in chat; the verb has no prompt of its own, because an agent has no terminal to answer
it, and `--accept` is the act that spends.

Each reviewer starts in a snapshot of the reviewed revision (`git archive`, regular files and
folders only, in a temporary folder removed after the run) that leaves out the files and folders a
harness of the table loads as instructions or configuration (`AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, `opencode.json`, `.cursorrules` and the like, and the folders `.claude`, `.codex`,
`.gemini`, `.agents`, `.cursor`, `.opencode`), so that the revision under review does not instruct
its own reviewer through those inputs; the diff and a named file still carry them, as data. The
list holds what the documentation and the research read name, and an input they do not name stays
`UNVERIFIED`. For Codex and Claude the standard input is the prompt file. The prompt holds the lens, the output form, and the diff and the named files between lines
marked with a random token that the data does not hold, with the statement that the data is to be
examined and holds no instructions to the reviewer. Named files carry line numbers. The harness
rows keep each reviewer read-only: Codex `-s read-only` with no session kept and no user config or
rules loaded; Claude `-p` with `--bare` where `ANTHROPIC_API_KEY` is set (the documented mode for scripted calls;
it reads no login, so the run bills the key, and the plan says so) and else `--restricted
--safe-mode`, with the tools `Read`, `Grep` and `Glob`, the writing and
command tools denied by name, permission mode `dontAsk` with no one to answer a prompt, no MCP
server and no skill. No flag turns off Claude's session record: a reviewer's session is kept like
any other. The instruction files in the person's own home are not isolated; the
files of the revision are. Cursor and OpenCode are
table rows with `read_only_confirmed` false: their documentation names read-only modes or
permission keys but not what they cover, and gives no way to skip the folder's own instructions
and configuration. The plan prints `READ-ONLY NOT CONFIRMED BY DOCUMENTATION` for each; neither is
in the default council, so each is run only where the person's plan names it. Neither documents
standard input, so the prompt is their last argument (`prompt_via` argument; standard input is
closed), and each has its read-only settings given by environment variables the plan prints. A multi-line argument through a Windows `.cmd` shim loses its newlines, so these two rows are `UNVERIFIED` on Windows and their accepted-run test is skipped there.
A
reviewer that does not start, exits non-zero, passes the timeout (its process group is killed),
writes no answer or an empty one, whose answer does not begin with `Verdict: FAIL`,
`Verdict: UNVERIFIED` or `Verdict: PASS`, or whose verdict is `FAIL` with no finding in the form,
is reported with its reason and writes no review file; the others go on. The run prints each
reviewer's verdict and finding count. A `PASS` or `UNVERIFIED` verdict over a body that says the
reviewer could not read the code is filed, since no check can tell it from a clean review; the
acting agent reads each file.

A review file is `<run folder>/<tag>-<harness>.md` (tag `r1`, `r2`, in the order given): the
engine's line `Reviewed: <full revision>`, a title, then the reviewer's answer. Lines of the answer
that start `Reviewed:` or `Disposition:` outside a code fence are left out, and a note says how
many, because the first is the engine's to write and the second belongs to whoever acts on a
finding. A fresh file reads FAIL under `review check` (`DISPOSITION_MISSING`) until dispositions
are written, and `review sweep` therefore holds a release back while a council's findings stay
open. The default run folder is `.agents/work/council/<revision>/`; it also holds `council.json`
(each reviewer's argv, status, seconds, the cost the harness reported, citation counts), and an
existing folder is refused, so a run never overwrites one.

Every `path:line` in a finding (the reference reader of `review since`, kept to references with a
line) is looked up at the reviewed revision, and in the text given for a named file. A path that
names no file, a suffix that names several, a line past the end of the file, and a finding with no
`path:line` get a line `Citation check: ...` under the finding's heading. Nothing is removed. The
run prints the counts. The lookup shows that a place exists in the revision, and not that the finding
is right.

Exits: 0 every reviewer wrote a file; 1 a refusal, or a reviewer failed; 2 a usage error.

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
| `outcomebound review sweep [DIR]` runs `check` on every review file of a work folder (default `.agents/work`): each `.md` file one to four levels below it that holds a `Reviewed:` line outside a fence, whatever its headings, so a review whose headings are malformed is read and fails rather than drops out. It enters no linked folder, reads no linked file and no file over 1 MB, counts each file it did not read on its first line and names them with `--verbose`. The result also keeps the `Reviewed:` ref each file says it read, which `outcomebound where` uses to tell the reviews of a branch. Its first line is the verdict and the counts; `--json` adds an optional `files` object to the same report. `make release-check` runs it on the main checkout's `.agents/work`, resolved from the Git common directory, so a release cut in a worktree reads the reviews other sessions left; CI does not, since a clone holds no `.agents`. A report with no `Reviewed:` line is not read: its issues reach a release only as milestone issues (field: a review another session left with open findings was not seen while pull requests merged and a release was drafted) | a ledger file of known issues, a second place to forget; a date filter, which hides an old open finding; selection by finding headings alone, which reads decision briefs as reviews; a walk of the whole folder, which on a working machine reads hundreds of thousands of files | agent | decided |
| `outcomebound review council` is a verb with `--plan`, which prints and runs nothing, and `--accept`, which runs, and a short skill `review-council` that tells the agent to show the plan and get the person's yes before `--accept`. The skill carries when a council is worth its cost; the verb carries the argv, the read-only flags, the timeout, the snapshot and the file format. The agent, not a model, judges and merges findings (maintainer, 2026-10-18; field: a review from another harness or model is asked for often, and was run with hand-written calls, each with its own flags and each a chance to omit a read-only one) | a skill with no verb, which leaves read-only, a timeout and the input guard to an agent that may skip them; a verb that also merges the findings by a model call, which adds spend and a second unreliable reader; a prompt in the verb for a yes, which an agent without a terminal cannot answer and a script can answer for the person | user | decided |
| For Codex and Claude the prompt goes in by standard input from a file the verb writes, and not by an argument with standard input from `/dev/null`; Cursor and OpenCode take it as the last argument, with standard input closed, since they document no standard input. A diff can pass the size an argument may have; the prompt file ends, so the reviewer cannot wait for more input, which is what `/dev/null` was to guarantee | the prompt as an argument; an open pipe, on which a reviewer waits | agent | assumed |
| The reviewer reads a snapshot of the reviewed revision made with `git archive` in a temporary folder, not the person's work tree. The reviewer sees the revision the review claims, no uncommitted file, no `.git` and no hook of the work tree; a write by a reviewer reaches a folder that is thrown away. `review sweep` and Git never read it. The snapshot leaves out the instruction files and folders of the harnesses, since a harness loads them as instructions and a change under review could edit them (found by the independent review of this design) | the work tree as the working folder, where a reviewer reads uncommitted text and a project's own settings; `git worktree add`, which writes to the repository | agent | assumed |
| Claude runs with `--bare` where `ANTHROPIC_API_KEY` is set and with `--restricted --safe-mode` where it is not, always with a tool list of `Read`, `Grep` and `Glob` and the write and command tools denied by name. `--bare` is the documented mode for scripted calls and skips hooks, plugins, skills, MCP servers and instruction-file discovery, but the installed tool's help says it reads no login and takes `ANTHROPIC_API_KEY` only, so the run bills the key and not the person's login (the maintainer accepts that for limited use, 2026-10-18); the plan says which login a Claude reviewer uses. Without a key, `--restricted` ignores the settings files and removes the command tools, and `--safe-mode` disables plugins, hooks and instruction files; the help of `--safe-mode` says the login still works, and for the two together it is `UNVERIFIED`. Which variant was verified: neither, and whether any of these flags stops a write is `UNVERIFIED` until a harmless run the maintainer asked for shows it | `--bare` alone, which fails for a person logged in without a key; `--dangerously-skip-permissions` or any bypass flag, which the table test refuses; a hook-disabling settings string, which leaves the other settings loaded | user | decided |
| The built-in default council is one reviewer, `codex:gpt-6-astra:high`. The verb reads an optional council file, the project's `.outcomebound/council.json` first and the `.outcomebound/council.json` in the person's home folder if the project has none, and `--reviewer` wins for a run; the plan prints which of the three supplied the reviewers (maintainer, 2026-10-19). A model name changes faster than this file, so the default is an example that a file or a `--reviewer` entry overrides. The adopt skill asks the adopter once, offering the default, and writes the project's file only if they name other reviewers. The ruling of 2026-10-18 for a default of five reviewers was replaced: five reviewers at the person's expense is too many for a default, and a project that wants a council names it | a default of one reviewer for each harness; a default of five; a file merged from both places, where the person cannot tell which source ran; the person's file before the project's, which a committed choice could not set | user | decided |
| The flags are data in `adapters/council.json`: each with its reason, its source, the day it was read, whether the installed tool's help listed it (`codex exec --help` of codex-cli 0.163.0 and `claude --help` of Claude Code 2.1.302, both read 2026-10-18, with no model run) and whether a run showed its effect (`tested` or `UNVERIFIED`; all are `UNVERIFIED` because no run was asked for). A harness is a row. The table holds Codex and Claude, and Cursor and OpenCode as unconfirmed rows (maintainer, 2026-10-18; their headless facts, read 2026-10-18, are in the research record). Gemini CLI has no row: its read-only plan mode is documented to switch to unrestricted approval when a plan runs headless, the folder's `GEMINI.md` and hooks have no documented switch, and it has been offered only to paid, Enterprise and API-key users since 2026-06-18, so a read-only setup is not confirmed. Copilot has none (maintainer). The model ids in it are examples that change faster than the file | flags in the code, where a change of a tool needs a code change; a model default stated as a rule (it is an example that a `--reviewer` entry overrides) | agent | assumed |
| An answer must begin with a `Verdict:` line, and a `FAIL` verdict needs a finding, or the reviewer is `unreadable`, the answer is kept as `<tag>-<harness>.raw.txt` and no review file is written. A model that refuses or answers off the form would otherwise leave a file with no finding, which `review check` passes. The prompt puts the list of what was not read under a `## Not read` heading, so that its paths are not read as the last finding's citations | filing every answer; guessing findings from prose | agent | assumed |
| Citations are looked up, flagged and kept, never removed. A finding with a place that is not in the revision may still be right about another place, and a count of flags tells the acting agent where to read first | dropping a finding with a missing path, which hides a claim a reader would want to see; a model call to repair the citations | agent | assumed |
| The verb sets no spend cap and no run stop of its own choosing: `--budget-usd` is the person's number, passed to Claude's `--max-budget-usd` where the person gives one, and the timeout is the table's, from a Codex run seen to take up to thirty minutes (a public skill's page, read 2026-10-18; no source for a Claude run, `UNVERIFIED`). Codex has no spend cap flag in the installed help, so its timeout is its only bound, and the plan says so | a default cap or a round count chosen without evidence | agent | assumed |

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

`tests/test_review_council.py`, with stand-in `codex` and `claude` programs on `PATH` (a test fails
first if a real one would run): the plan names each reviewer, its argv and safeguards and starts
nothing and makes no folder; the budget flag is in the argv only when given; reviewer entries parse
with defaults and refuse a part that could start a flag; an accepted run starts each reviewer with
the read-only flags, in a snapshot with no `.git` that is removed after, the prompt on standard
input with the diff after the opening marker; the review file starts with the engine's `Reviewed:`
line, drops a reviewer's `Reviewed:` and `Disposition:` lines outside a fence and keeps one inside,
reads FAIL for missing dispositions only, and PASS once they are written; citations to a missing
file, past the end and none are flagged and every word stays, and a named file is checked against
the text given; a failed, empty, timed-out, missing and unreadable reviewer are each reported while
the other writes its file and no file stands for the failed one; an existing run folder is refused
with nothing started; every bad request is refused with its reason; the table holds a source and a
read day for each flag and no bypass flag. Stand-in `cursor-agent` and `opencode` programs show the prompt as the last argument with standard input closed, the environment variables set, the plan's unconfirmed-read-only line, and that effort-less harnesses refuse an effort part; the default council holds no unconfirmed harness; `--bare` appears only where an API key is set, and the plan never prints the key, and the text of a reviewer's standard error that a failure report prints has the value of any environment variable named like a key, token, secret or password replaced. No test starts a real `codex`, `claude`, `cursor-agent` or `opencode`: what the
flags do on a real tool is `UNVERIFIED` until a run the person asked for shows it.
