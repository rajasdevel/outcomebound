---
last_checked: 2026-10-01
volatility: STABLE (method and measurements) / VOLATILE (§3 GitHub mechanics, §7 rendering and §8 work sources change with tool and product releases)
sources:
  - https://docs.github.com/en/graphql
  - https://cli.github.com/manual/gh_issue_edit
  - https://git-scm.com/docs/git-patch-id
  - https://docs.gitlab.com/user/project/merge_requests/commit_templates/
  - https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams
  - https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections
  - https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors
  - https://github.com/anthropics/claude-code/issues/14375
  - https://cursor.com/changelog/cli-feb-18-2026
  - https://linear.app/docs/mcp
  - https://developer.atlassian.com/cloud/rovo-mcp/
  - https://developers.notion.com/guides/mcp/overview
  - https://docs.slack.dev/ai/slack-mcp-server/
  - https://developers.google.com/workspace/meet/api/guides/artifacts
  - https://developers.google.com/workspace/calendar/api/guides/version-resources
---

# Tickets on a tracker: acceptance, evidence and landing

How a ticket layer for coding agents runs on an issue tracker and on the other places work arrives
from: acceptance, what to ask a person, evidence, landing, and writing back.

Re-check when `gh` or GitHub's GraphQL schema changes the fields or relations a reader uses, a
harness changes what its surfaces render, or a connector named in §8 changes what it can read or
write.

This reference answers how a ticket layer for coding agents can run on an issue tracker: how a
person's acceptance and confirmation are recorded, what a person should and should not be asked,
how evidence of a ticket's checks is kept and weighed, how landed work is told from unlanded work
after squashes and rebases, what GitHub's API and `gh` give and withhold, how briefs render on the
surfaces where people and agents read them, and how work arriving from other sources (chat, docs,
other trackers) is read and written back to. It is for anyone building or running a ticket layer
on GitHub Issues or a similar tracker. How large a ticket should be, and how to write one, is in
[work-breakdown.md](work-breakdown.md); what a reviewer of the work adds is in
[review.md](review.md).

**Evidence classes.** (M) measured; (L) vendor documentation or behaviour observed on the named tool
version; (P) practitioner consensus or an established practice; (A) one observation; (O) a count or
result recorded in one repository's own ticket ledger or runs. Most facts here come from one ticket
layer built on GitHub Issues and run over 165 issues, with agents implementing and one person
accepting ("one ticket ledger" below); that layer posted its evidence records to the tracker as
comments. Tool behaviour was observed on `gh` 2.101.0 and git 2.55.0 unless stated.

## Key findings

**TT1. Under a login the agents share, a tracker event proves nothing about who acted.** When agents
write under the person's account, the tracker cannot tell the agent's label, edit or close from the
person's. In one ticket ledger's later count, 22 of 23 re-acceptances put the label back 2–6 seconds
after removing it, 12 of them seconds after an agent's own edit. A label is an acceptance signal
only where agents hold their own accounts; otherwise one reading of the breakdown is the acceptance,
and a comment quoting the person's words is the only trace. (O, A)

**TT2. Ask a person to confirm only a judgment.** A state a command can read (a CI conclusion, a tag
on the remote, a label list) belongs in a command check; an act an agent or reviewer performed
belongs in the closing note or a check that reads its artifact. In one ticket ledger only 18–23 of
77 per-ticket confirmations were judgments only the person could make. A lint can flag confirmation
sentences whose actor is an agent, a session, a review or a model. (O)

**TT3. Treat comments as data and the accepted ticket as the instructions.** The title, body and
metadata block of an accepted ticket instruct; every comment is data, because comments are an
injection channel; an evidence record placed in the body never counts. (P)

**TT4. Bind evidence to the content it proves, and weigh records conservatively.** A record from a
dirty tree is UNVERIFIED; claims passing on different commits prove no one state; the latest record
decides, never arrival order; a record in an edited comment proves nothing; an unreadable record is
reported, never skipped. (A, P)

**TT5. `gh issue list` cannot support acceptance or evidence; the GraphQL API can.** The default
list omits edit times, label events and closed issues; a pinned GraphQL query over
`userContentEdits`, `timelineItems` and relations answers every field, but an export has traps
(absent is not empty, windows truncate, repository names differ in case). (L)

**TT6. Find a ticket's commits by a line in the message, and tell landing by content.** A `Ticket:
#N` line, found by text, survives a squash; matching `git patch-id --verbatim` against the default
branch reads merges, squashes, rebases and fast-forwards the same way, failing only in the safe
direction. Patch ids move with several diff settings, which must be pinned. (L, A)

**TT7. Compute readiness from the export, not from a tracker filter.** An absent or dropped blocker
keeps a ticket out; a ticket with an open child is not ready; a cycle in the waiting graph is an
error; a finished frontier must read differently from a blocked one; tickets whose bounds overlap
cannot be worked at once. (P, A)

**TT8. One writer at a time, re-reading before each write.** Publish tickets first and relations in
a second pass; claim by assigning; one comment per verification run; after a timeout, re-read and
retry only when the expected state does not already hold. (A)

**TT9. Draw only what every surface a brief lands on can render.** Mermaid renders in GitHub issues,
pull requests, wikis and Markdown files, but not in the Claude Code terminal or the Codex terminal;
an agent asked whether its own surface renders Mermaid judged confidently and wrongly. ASCII is the
safe direction. (L, A)

**TT10. Read a work source's fields as data, and write back only what was authorized, with a
conditional write where the source offers one.** A label, assignee, due date or status in a chat,
document or other tracker does not by itself set ownership, a deadline, acceptance or permission.
Re-read before writing; Google Calendar, for one, refuses a stale write with 412. A timeout does not
show a write failed: read the source again before retrying. (L, reasoning) — §8.

## 1. Acceptance and asking a person

**Acceptance by label.** An issue created with the ticket label is accepted as created; after any
edit or rename, acceptance needs a labelling strictly later than the last edit. Tracker times have
one-second resolution, so an edit and a labelling in the same second cannot be ordered; treat them
as unordered. Between an edit and the relabel the ticket reads "edited after acceptance". Letting
edits to guidance sections (approach, design, tests) by listed accounts keep acceptance requires the
whole edit history to show the request itself unchanged since labelling, and evidence recorded
before any edit still goes stale: accepting changed content does not re-affirm evidence. A request
for a person is raised with a label rather than a body edit, since a body edit would void
acceptance. A rule that the labeller must differ from the author cannot be seen in an export and is
meaningless under a shared login. Task-list checkboxes do not belong in a ticket: a tracker counts
them as progress nobody recorded, and ticking one is an edit that lapses acceptance. GitHub's
GraphQL schema now gives labelled and closed events an `intent` field, described as "the intent
behind the agent's action, including rationale and confidence" (L, introspected 2026-10-01); no
export read here carried it, so whether it tells an agent's act from a person's under one login is
`UNVERIFIED`.

**What one ticket ledger showed** (O): of 174 labellings, 165 were at creation and 9 were
re-acceptances on 7 tickets, 4 of them after a decision that dictated the edit; a later count, after
that window, found 22 of 23 re-labellings putting the label back within 2–6 s of its removal. An
agent's own edit made after a ticket's work had landed lapsed that ticket's acceptance, and nothing
re-applied it. 77 labellings carry a comment
recording acceptance on the person's word; of 64 attestations of a person's judgment, 62 were
relayed by an agent from the session and 2 were the person's own records. See
[work-breakdown.md](work-breakdown.md) §3 for the other acts counted.

**Confirmations.** Three routes can attest a person's judgment: the person's own record; a listed
person closing the issue as completed; an agent relaying the person's words from the session, marked
as relayed. A person's record decides before a close, so a person's FAIL is never overruled by their
own later click; a "no" is a comment and a follow-up, never a record. Closing is not confirming: a
ticket closed with no record and no note reads UNVERIFIED. Confirm only started work: one rundown
asked the person to confirm two tickets nobody had begun; a ticket with no command check is
put to a person only once a closing note exists. A confirmation of wording needs the wording in the
request; items without it came back "need more context". Name what is asked in plain words: a
request that named an internal id (a row of a spec's decision table) without saying what it was drew
a request to explain it before deciding, and a confirmation whose rundown named tickets only by
number and checks only by internal name went unanswered until the rundown named each ticket by its
title and said what each check guards against (A). Work
may stack on a blocker awaiting confirmation to a declared depth (one was used). For an open ticket
whose work has landed, the next act is the person's; telling anyone to close it would forge a
confirmation where agents act under the person's account. A warning a person learns to skip costs
more than giving none (reasoning).

**The rundown put to a person.** Group items by kind (decide, accept, confirm, held), and within a
kind put first the ticket more others wait on. One yes may cover all confirmations and every
reversible recommendation, naming the ids; scope changes are answered separately, and an
irreversible edge is never batched. A decision is reversible only if it is not an edge, grants no
authority, changes no scope, and can be undone entirely inside the repository; anything that writes
to a tracker, remote or registry, or loosens a gate, is not. Ask once: pre-fill defaults, run the
lookups first (such as label-name collisions), attach the commands, and take a single yes, so a
person with no preference answers in one word. Show a decision that waits on an earlier answer in
the first round too, marked as waiting: an interview that revealed such decisions only after the
earlier answers refused a person who had answered every question shown, then put a third round to
them (A). State an inferred confidence as a number marked as inferred, and a fact as a
fact: words of likelihood are read as very different numbers. Analysts asked what "serious
possibility" meant gave odds from 20% to 80% (Sherman Kent, "Words of Estimative Probability", 1964)
(A), and of 1,700 people surveyed, 90% put "likely" between 55% and 90% and "real possibility"
between 20% and 80% (Mauboussin and Mauboussin, Harvard Business Review, July 2018) (M); both read
on 2026-10-01 through a secondary account, since the primary pages did not render. Answer ids use
the ticket's own id, not its position in the list, so an answer given later still names the same
ticket after another has closed. In one ticket ledger an end-of-run list of about 23 items held
about 11 that asked for nothing, and 8 of 10 open tickets waited on a person or on nothing (O).

**When an agent asks.** Only on a met stop condition, missing authority or an irreversible edge, a
gap in intent, or a stale requirement link; a failing check is never a reason to ask. A request ends
that ticket's turn, never the run. An agent never grants or lifts a hold, removes a blocker, or drops
a ticket.

## 2. Evidence records

- **Content identity.** Hash the decision content (title, brief, decision keys) as written, lists as
  lists, because any joined form collides; hash refused values too. Evidence binds to that identity;
  lifecycle facts (labels, assignees, state) do not change it (P).
- **Weighing.** A record from a dirty tree is UNVERIFIED. Claims passing on different commits prove
  no one state. The latest `at` time decides, never arrival order; differing records within one
  second conflict, and the remedy is another run. Future-dated records are refused. A record in an
  edited comment proves nothing. An unreadable record is reported, never skipped: a FAIL edited into
  nonsense would otherwise hand the decision back to an older PASS. A record that omits a field reads
  as not re-derivable; leaving a field out is never better than filling it in (P, A).
- **Observed traps** (A):
  - Post a record, not raw output: a tool's whole output, posted as is, put a local filesystem path
    into 19 tracker comments, and trimming them counted as edits, so those records proved nothing
    until posted again untouched.
  - An unset CI variable passed as an empty base ref produced a green run that compared nothing.
  - A check that rewrites tracked files leaves every later check in the run UNVERIFIED; a check that
    changes and restores a file before exiting is not seen at all.
  - One record per verification run, inside or beside the closing note, was enough; in the ledger,
    197 comments held 642 records and 51.7k words.
  - In one ticket layer, of the 11 codes that weighed records, 2 fired in real use; of the layer's
    70 message codes, 26 fired in real runs and 44 only in tests and evals.
  - A warning that fires on records which by nature cannot satisfy it buries the others: in one
    audit 23 of 45 WARNING rows were a bounds warning on a person's attestation, which names no
    commit range, and a first reading of that audit took every WARNING as intended behaviour.
- **Records outlive engines.** Formats evolve by block version, and a reader reads every earlier
  version.

**Requirement links.** A requirement row carries a revision, bumped when its meaning changes and not
for a typo; a ticket cites the revision it was written against. A lower citation on an open ticket
is a stale link, needing a re-read and re-acceptance; a statement change without a bump, or a
changed cited section, is warned. Compare rows cell by cell with each cell stripped: re-padding a
table otherwise flagged about 70 rows. A brief marks a stale link rather than refusing, because a
refusal would hide the very row the person needs to read. What is consumed across a boundary (by a
ticket's author, a tracker, CI or a second command) lives in the spec, not in a ticket; ticket count
is an unstable test of where a contract lives.

**The closing note.** Four lines written at close, while the context is fresh: delivered; decided
beyond the brief; surprises; follow-ups. The decisions and follow-ups are gathered for the next
breakdown. Closed tickets are archived and summarised, and an agent reads the summary rather than
the archive unless a task names a ticket. In one ledger closing notes had a median of 155 words (O).

## 3. GitHub mechanics (VOLATILE)

**What `gh issue list` omits.** It exports neither edit times nor label events; by default it
returns at most 30 issues and only open ones, so an audit read from its default output sees nothing
closed and passes vacuously; an edited comment shows no editor (L, `gh` 2.101.0 [as-of 2026-09-19];
the defaults unchanged in 2.102.0's help, read 2026-10-01). `gh issue edit` sets relations by issue
number: `--parent`, `--add-blocked-by` and `--remove-blocked-by` (2.101.0) [as-of 2026-09-29], with
`--add-blocking`, `--remove-blocking` and `--remove-parent` beside them in 2.102.0 (read from
`--help` 2026-10-01; not run against a tracker) (L).

**The query that answers.** `gh api graphql --paginate --slurp` writes an array of pages. Fields used
(validated against an empty repository and a populated one [as-of 2026-09-20], and `CLOSED_EVENT`
against a live export of 29 issues [as-of 2026-09-21]; every field answered):

- `issues(first:50, states:[OPEN,CLOSED])` with `number title body state stateReason createdAt
  closedAt updatedAt lastEditedAt url author`;
- `assignees`, `labels`, `blockedBy`, `comments(first:100)`, `parent { number repository {
  nameWithOwner } }`, `subIssuesSummary { total }`;
- `userContentEdits { editedAt deletedAt editor diff }`;
- `timelineItems(last:100, itemTypes:[LABELED_EVENT, UNLABELED_EVENT, RENAMED_TITLE_EVENT,
  CLOSED_EVENT])`, each with `createdAt` and actor.

**Reading an export safely** (A):

- A connection absent from the document is unknown, never empty; a page flag of `null` is not "no
  further page"; a connection reporting a further page means the export is truncated.
- Compare `nameWithOwner` with the declared repository case-insensitively; an export of another
  repository was otherwise numbered as this one's.
- A parent or blocker in another repository, or a `subIssuesSummary.total` above the children the
  export holds, must never be read as local or closed.
- CLOSED with `stateReason` NOT_PLANNED or DUPLICATE means dropped. Whether a close was completed
  comes from the issue's state, not the closing event's own reason, which older closes leave empty.
  The closing event rides in the same last-100 timeline window as label events, so it can be
  truncated. Every closed issue in the tested repositories carried a closing event with a login; an
  issue transferred from another repository is UNVERIFIED.
- `IssueStateReason` holds `COMPLETED`, `NOT_PLANNED`, `DUPLICATE` and `REOPENED`, and
  `ClosedEvent` carries `actor`, `createdAt` and `stateReason` (L, introspected with `gh` 2.101.0
  on 2026-09-21 and again on 2026-10-01). Read a reason as free text: a reader whose schema
  enumerates the reasons refuses the whole export the day the host adds one. Where an issue was
  closed more than once, the latest closing event by its time decides, never its place in the
  document. How a deleted account appears (a null author or actor, or a placeholder account) was not
  observed and is `UNVERIFIED`.
- `userContentEdits.diff` was the whole body of each revision [as-of 2026-09-26]. A usable history
  has no deleted revisions, starts at `createdAt`, and ends at `lastEditedAt` with the current body.
  Times have one-second resolution; truncate before comparing.
- A 5.4 MB export was 44% bodies, 39% comments and 13% edit history.

**Limits and relations.** An issue body is capped at 65,536 characters. Compiled briefs quoting
every cited section verbatim ran 1,963–9,135 words (177–574 lines) across 22 accepted tickets, one
draft compiled to 15,014 words and 922 lines, and one draft exceeded the cap and could not be
posted (O). On GitHub only accounts with triage permission or higher can apply
labels. Setting relations through REST needs each blocker's database id first, then a POST to
`sub_issues` and to `dependencies/blocked_by`; relations written that way read back as the intended
graph. `gh issue edit` does the same by issue number (above). Drafts name each other by file name,
since nothing has an id before publishing, and become native relations when published. Collapsed
`<details>` sections keep their full content in the GraphQL `body` and in `gh issue view --json
body` [as-of 2026-09-23]; a blank line after `</summary>` is needed for Markdown inside to render,
and the block collapses only on rendered GitHub.

**Renaming a label.** A label is one object: the `updateLabel` mutation names it by its node id
and sets an updated `name`, and a `LabeledEvent`'s `label` field references that object (L, GitHub
GraphQL schema, introspected 2026-10-01). A rename therefore follows the label onto every issue
that carries it, and nothing needs relabelling by hand. What a rename breaks is a reader that
matches labels by a configured name: the issues carrying the label, and the labelling events that
record acceptance, holds or requests, stop matching until its configuration is renamed in the same
step (reasoning, checked against one ticket layer's code).

**The workflow document.** GitHub shows a link to `CONTRIBUTING.md` to anyone who opens a pull
request or creates an issue (L, GitHub Docs, "Setting guidelines for repository contributors", read
2026-10-01), but no coding-agent vendor documented its agent reading that file unprompted (L, URLs
not recorded) [as-of 2026-09-19]. How work lands reaches an agent only through a pointer in its
instruction file, and lines in `CONTRIBUTING.md` that an agent would not need still serve its human
readers.

**Hosted CI and a tracker.** A workflow that ran only for the default branch and pull requests into
it was run on a branch through a draft pull request marked not for merging. A run the host refuses
before its first step (quota or billing) reads UNVERIFIED, not FAIL. On a private repository on
GitHub's free plan, branch protection and rulesets are not available (the API answers 403 "Upgrade
to GitHub Pro or make this repository public"), so a `CODEOWNERS` line there guards nothing.

**Other trackers.** No reader or fixture was built for Linear or Jira, and no claim is made that a
mapping works (UNVERIFIED); what their connectors document is in §8. A ticket store kept as files
in the repository records no acceptance event and no closing actor, and a claim on a ticket is an
edit on a branch that other branches cannot see until it lands, so such a store suits one agent at
a time; parallel agents need a tracker's shared assignment (A, a file store built and run end to
end in scratch clones).

## 4. Landing: finding a ticket's commits

- **The ticket line.** `Ticket: #N` opens a line of the commit message, and may be indented or
  list-marked, as a squash writes it; it is found by text, never parsed as a git trailer; cited inside
  a sentence it names nothing. A subject ending "(#N)" was also read for sizes and bounds. `git log
  --grep '^Ticket: #N'` finds them. GitLab's default squash commit message is the template
  `%{title}`, the merge request's title alone, so on GitLab the line survives a squash only where
  the template or the title carries it (L, GitLab commit-templates documentation, read 2026-10-01;
  not reproduced).
- **Landed by content.** Where history does not show ancestry (after a squash or rebase), match `git
  patch-id --verbatim` of `base..commit`, or of each non-merge commit as one contiguous run in
  order, against the default branch's first-parent history. Merge commits, squash, rebase and
  fast-forward all read the same verdict; the two cases that rewrite the commit land by content.
  Without `--verbatim`, `git patch-id` strips whitespace, so two changes that differ only in
  indentation share an id. In scratch repositories [as-of 2026-09-19], after a squash merge onto a
  base that had moved, the branch's commit was absent from the default branch's history and the trees
  differed, while the change's patch id equalled the squash commit's; after a rebase every
  per-commit patch id reappeared (A).
- **Known misses, all in the safe direction.** Two tickets squashed into one commit, and parts
  interleaved with another ticket's commits, read not landed; a range holding a merge records no
  parts (a merge's own resolution is in no part), so rebasing it commit by commit reads not landed. A
  branch deleted after a squash, a cherry-pick and amended commits were probed and read as intended.
  Failure is only ever a false "not landed".
- **Checkouts that cannot tell.** A shallow clone lacks the history ancestry and patch ids need, and
  a git whose `patch-id` lacks `--verbatim` cannot compute them, so both read unresolved, never "not
  landed", wherever the verdict turns on a patch id; a commit that is an ancestor of the default
  branch reads landed under any git. Observe these conditions in the checkout being judged, on each
  run: an index of patch ids built in a full clone and reused in a `--depth 1` clone made a change
  read landed (A, git 2.55.0) [as-of 2026-09-20].
- **Pinning patch ids.** Settings that moved patch ids: `diff.noprefix`, `diff.mnemonicPrefix`,
  `diff.srcPrefix`/`diff.dstPrefix`, and `core.abbrev` for hunkless diffs without `--full-index`. A
  user's `format.pretty` hid commits from `patch-id` unless `git log`'s format was explicit.
  Forty-five further configuration keys on git 2.55 moved nothing. A working-tree `.gitattributes`
  and `.git/info/attributes` cannot be pinned. Isolating git from user configuration is not an
  option, because `safe.directory` lives only there. That one change gets equal ids on two machines
  is UNVERIFIED; CI on Linux showed only that the tests pass (L, A). The producer pinned in full:
  `git -c core.quotePath=true -c diff.algorithm=myers -c diff.renames=false -c diff.noprefix=false
  -c diff.mnemonicPrefix=false -c diff.srcPrefix=a/ -c diff.dstPrefix=b/ diff --no-ext-diff
  --no-textconv --no-color --unified=3 --full-index <from> <to>`, piped to `git patch-id
  --verbatim`, with a root commit diffed against the empty tree. Name an excluded directory with
  `literal` pathspec magic (`':(top,exclude,literal)<dir>'`): read as a pattern, a directory named
  `ticket*` also excluded `tickets_runtime/` (A).
- **Cost.** A patch-identity audit over one ledger took 7 min 39 s and reported 290 unnamed commits
  in range and 154 out-of-bounds findings; 66 of 150 closed tickets read "not clean". The ticket
  line with `git log --grep` answered the same question cheaply (O).
- **A stale base.** A record's base can lag far behind the branch, and a range from it holds every
  ticket landed since: in one ledger, bounds judged over each record's range from its base warned 55
  of 165 tickets out of bounds 17,233 times, mostly for other tickets' work (O). Reading
  only the commits that name a ticket lets unnamed work through, so read both: the commits naming
  the ticket plus the range cut at the oldest naming commit. Verifying after landing leaves no range
  to check.
- **The default branch.** Use the declared default branch, else `origin/HEAD`, else
  `init.defaultBranch`, and never a branch's upstream: judging against a branch nobody named is worse
  than reading unresolved.

## 5. Readiness and the waiting graph

- Readiness is computed from blocker states in the export, never from a tracker's own filter. An
  absent or dropped blocker keeps a ticket out; a ticket with an open child is not ready (P).
- Cycles are found in the waiting graph (ticket to blocker, parent to child); a child blocked by its
  own parent is a cycle. A frontier that is done is told apart from one that is blocked. Two failure
  modes vendors name for shared task lists: a task never marked complete blocks its dependents, and
  a lead decides the team is finished early (Claude Code agent teams, L) [as-of 2026-09-20].
- Report how many FAIL records a ready ticket already holds, so whatever drives a loop can stop
  returning to it.
- Two ready tickets whose bounds overlap cannot be worked at the same time; report such pairs.
  Only tickets on disjoint files run in parallel, and they are integrated one at a time (P).
- Performance traps met at small scale (A): reading a spec per ticket opened one spec 176 times for
  88 tickets; a quadratic bounds-overlap check took 6 s for 300 tickets with ten bounds each until
  cached; a history walk held 13.7 MB of patch text for 56 commits until piped; one unclosed code
  fence made evidence parsing quadratic until the fence scan became a single pass.

## 6. The write protocol

One writer per tracker at a time. Re-read the ticket before every write; after a timeout or an
uncertain response, re-read and retry only when the expected state does not already hold (A).

| Act | Writes |
| --- | --- |
| Publish | create each issue with the label; then set sub-issue and blocked-by relations in a second pass |
| Claim | assign to yourself |
| Record a verification | one comment per run |
| Ask for a person | a comment with the reason, the request label, unassign |
| Release after a failure or a change | a comment, then unassign |
| Close | the closing-note comment, then close as completed |

A pure person's act with no implementer work (tagging a release, creating labels, committing an
authorization record) is an item in the rundown or the release checklist, not a ticket with a brief,
a claim and a close; where the act needs preparing, the preparation is the ticket.

## 7. Rendering briefs on trackers and terminals (VOLATILE)

- Mermaid renders in GitHub issues, discussions, pull requests, wikis and Markdown files
  ([GitHub docs](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams))
  [as-of 2026-09-23]. The Claude Code terminal does not draw it
  ([issue 14375](https://github.com/anthropics/claude-code/issues/14375)); a Mermaid fence shows as
  raw text in the desktop app's tab ([issue 52517](https://github.com/anthropics/claude-code/issues/52517));
  the Codex terminal has no Mermaid rendering in 0.153.4 and 0.154.0
  ([agent-mermaid-hook issue 14](https://github.com/pretty-good-software-org/agent-mermaid-hook/issues/14));
  the Cursor CLI renders Mermaid inline as ASCII
  ([changelog, 2026-02-18](https://cursor.com/changelog/cli-feb-18-2026)); no Cursor page read says
  chat replies render it ([2.2 changelog](https://cursor.com/changelog/2-2),
  [cookbook](https://cursor.com/docs/cookbook/mermaid-diagrams),
  [forum](https://forum.cursor.com/t/mermaid-visualization-in-chat/59041)). All read on one day
  [as-of 2026-09-23].
- Identify the surface from the environment, not the agent's report: asked whether its surface
  renders Mermaid, an agent judged confidently and wrongly (A).
- Draw a diagram only where order, dependency or flow is the point; draw order as its transitive
  reduction, one chain per line, and a cycle edge by edge; fall back to ASCII, since a wrong guess is
  safe only in that direction.
- Never spell a mark as `[ ]`, `[x]` or `[X]`, which Markdown draws as a checkbox at a list item's
  head; do not indent four spaces, which renders as code. A heading followed by list items reads the
  same as plain text and as Markdown. The other layouts each failed on one surface: plain lines
  pasted into a Markdown view joined into one paragraph, which led agents to fence whole briefs; a
  hard break made with two trailing spaces is invisible and is stripped by editors and whitespace
  normalisation, and a trailing backslash shows on every line in a terminal, while a list item keeps
  its line in both (A) [as-of 2026-09-23]. A layout aligned in columns breaks in a Markdown view's
  proportional font, and box-drawing characters are not ASCII (P).
- Markdown parsers and renderers disagree: a heading planted inside an HTML comment turned request
  text into editable guidance under a section cut. Treat a brief as one unit where it holds `<!--`,
  HTML blocks (bare `<details>`/`<summary>` excepted), unclosed fences, setext underlines, or fences
  inside lists or quotes. A brief that shows a metadata sentinel must fence it, or a parser reads it
  as a malformed block.
- A title carrying a line end forged header lines in a compiled brief; keep a heading to one line.
  An absolute path of the authoring machine leaked into a brief handed to another session; strip
  machine paths from anything handed on.

## 8. Work sources beyond the tracker (VOLATILE)

Work also arrives from chat, documents, meetings and other trackers. What their connectors can
reach, as each vendor documented it (L, pages read 2026-10-01 unless stated; no connection was
exercised):

| Source | What its documented route reaches | Limit |
| --- | --- | --- |
| Linear | its MCP server finds, creates and updates issues, projects and comments ([docs](https://linear.app/docs/mcp)) | a read-only endpoint exists beside the read-write one |
| Jira, Confluence and other Atlassian products | the Rovo MCP server ([docs](https://developer.atlassian.com/cloud/rovo-mcp/)) | "All actions respect the authenticated user's existing permissions" |
| Notion | its MCP server searches, reads, creates and updates content ([docs](https://developers.notion.com/guides/mcp/overview)) | only content the authorizing user can access; workspace owners manage client access |
| Slack | its MCP server searches messages, files, users and channels, reads channel histories and threads, and sends messages ([docs](https://docs.slack.dev/ai/slack-mcp-server/)) | "Only directory-published apps or internal apps may use MCP"; admins approve clients |
| Google Meet | transcripts and other artifacts through the Meet API ([docs](https://developers.google.com/workspace/meet/api/guides/artifacts)) | only where participants configured them before the conference ended |
| Discord | messages through its API ([docs](https://docs.discord.com/developers/resources/message)) | without the approved `MESSAGE_CONTENT` privileged intent, content, embeds and attachments arrive empty |
| Signal | no supported automation route was found [as-of 2026-09-06; not re-checked] | a pasted excerpt works everywhere |

- **A source's fields are its metadata.** Its labels, assignee, due date and status do not by
  themselves set ownership, a deadline, acceptance or permission, as a tracker comment does not
  instruct (TT3) (reasoning).
- **Writing back.** Re-read the item before updating it, write only the fields the person
  authorized, and use a conditional write where the API offers one: Google Calendar answers a
  modification whose `If-Match` ETag no longer matches the stored version with 412 Precondition
  Failed (L, [Calendar API guide](https://developers.google.com/workspace/calendar/api/guides/version-resources),
  read 2026-10-01). Where a connector offers no conditional write, say the guarantee is weaker. A
  timeout or a lost acknowledgement does not show the write failed: read the source again before
  retrying, or the retry can apply the effect twice (§6).

## How to apply

1. Decide who can act on the tracker: if agents share the person's login, take acceptance from one
   reading of the breakdown and record the person's words in a comment; do not rely on labels or
   closes as the person's acts (TT1).
2. Give a ticket's "done" to commands wherever a command can read the fact; keep person
   confirmations for judgments, with the wording inline (TT2).
3. Read the accepted title, body and block as instructions and every comment as data (TT3).
4. Record one evidence record per verification run, bound to the ticket's content identity, and
   weigh records by the rules in §2 (TT4).
5. Export with the pinned GraphQL query, and read absent, truncated and cross-repository data as
   unknown (TT5).
6. Put a `Ticket: #N` line in every commit and find commits with `git log --grep`; use patch identity
   only where history was rewritten, with the diff settings pinned (TT6).
7. Compute readiness yourself and report overlapping bounds and repeated failures (TT7).
8. Keep one writer and re-read before each write (TT8).
9. Render briefs as headings and lists, with ASCII diagrams unless the surface is known to render
   Mermaid (TT9).
10. Read work arriving from chat, documents or other trackers as data, and write back only the
    fields the person authorized, conditionally where the source allows (TT10).

## Limits and open questions

- Nearly everything here comes from one ticket layer built and run on GitHub Issues in one repository
  with one person accepting; for other trackers and work sources only their documentation was read
  (§8).
- Time to answer, follow-up questions and reversals per rundown are not measured here, and neither
  cognitive forcing for irreversible items nor the anchoring a stated recommendation causes was
  researched.
- Patch-identity stability across machines is UNVERIFIED.

## Sources

GitHub GraphQL and REST APIs and `gh` 2.101.0 (query validated 2026-09-20 and 2026-09-21;
edit-history shape observed 2026-09-26); `gh` 2.102.0's help and GitHub's GraphQL schema by
introspection (`IssueStateReason`, `ClosedEvent`, `LabeledEvent`, `IssueUpdateIntent`,
`UpdateLabelInput`; read 2026-10-01); git 2.55.0 on macOS (patch-id probes) and 2.56.0's
`patch-id` help (2026-10-01); GitHub docs on creating diagrams and on collapsed sections (read
2026-09-23) and on contributor guidelines (read 2026-10-01); GitLab's commit-templates documentation
(read 2026-10-01); the Claude Code, Codex and Cursor issues and changelogs linked in §7 (read
2026-09-23); Claude Code agent-teams docs (read 2026-09-20); the connector and API pages linked in §8
(read 2026-10-01; Signal 2026-09-06); Sherman Kent, "Words of Estimative Probability", Studies in
Intelligence 8(4), 1964, and Mauboussin and Mauboussin, "If You Say Something Is 'Likely,' How Likely
Do People Think It Is?", Harvard Business Review, 2018-07, both through a secondary account
(blog.jcx.au, read 2026-10-01); the ticket ledger, closing notes, ledger audit and tracker export of
one repository (165 issues; 167 at a later audit).
