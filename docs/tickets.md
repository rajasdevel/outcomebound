# The ticket layer

`outcomebound tickets` reads a project's tickets from a tracker export and reports what they say.
It is opt-in and inert until the project declares a store: with no `.outcomebound/tickets.json`
every verb refuses, and nothing in OutcomeBound declares one for you. Each verb's flags are in
its `--help`.

## What it is, and what it never does

A ticket is an issue carrying the declared label: a title, a brief, and one `id=ticket v=1`
managed block — what it reads, its bounds, whether a person must do it, and the checks that say
it is done. The engine reads the issues from an export you produce and prints one report.

- **It calls no tracker.** It opens no network connection, reads no credential and writes
  nothing. Every report is about the export it was given, and says that export's age.
- **It runs nothing.** A `done-when` item names a claim of the committed claims plan, and the
  project's own gate runs it where the work lands.
- **It shapes the hand-off to the implementer.** A ticket is the same whoever builds it. A
  capable implementer decides which tests to write, when to run them and how to carry the work;
  a less capable one is handed more of those decisions already made, down to failing tests and
  stubs for a small model (the `hand-off-tickets` skill). The handover, the pull request or a closing comment,
  says what changed, each check's verdict, what was decided beyond the ticket, and the
  follow-ups found.

## Declaring a store

`.outcomebound/tickets.json`, one JSON object against `schemas/ticket-store.schema.json`:

```json
{"version": 1, "store": "github", "repo": "owner/project",
 "label": "ob-ticket", "human_label": "human-only", "request_label": "human-requested",
 "claims": ".outcomebound/ticket-claims.json"}
```

`label` is the gate and the acceptance: an issue is a ticket when it carries it, and no later
edit lapses it. Only accounts with triage access can label, so the declaration names no accounts.
`human_label` is a person's hold on a ticket; `request_label` is an agent asking for a person.
A `default_branch` key is accepted, and no verb reads it. Writing to the tracker is a separate
grant, recorded as `"writes": {"granted_by": "<username>", "on": "<date>"}` on the word of the
tracker's operator; without it an agent prints the tracker commands and a person runs them.

`claims` names one v1 validation plan committed in the repository, so claim names are one
namespace. A ticket's `done-when` names claims from it:

```text
done-when:
- tickets-report-contract
- tickets-docs
```

Each item names a claim; an item written `<claim>: red-first` is read as the claim alone. No
ticket waits on a person's confirmation: a fact a command can read is a claim, and the one human
judgment per plan is a person's go on the plan or goal, outside the engine. A `human:` item is
refused.

## The verbs

Every verb takes the checkout to read, `.` by default, and the export as `--input <file>` (`-` is
standard input). It exits `0` for PASS, `1` for FAIL or a refusal, and `2` for UNVERIFIED, a usage
error or a planning error. `check` prints one report, as text or under `--json`; `brief` prints
its document.

### `check`

`check [--draft <file>…]` reports what the open tickets say: whether each block is well formed,
each `reads` section resolves, each claim is defined, and the relations hold no cycle. A closed
or dropped ticket's links are history and are not resolved. `--draft` lints local draft files
together, relations included, and reads no store.

### `brief`

`brief <ticket> [--draft <file>…] [--detail full]` prints the document an implementer is handed:
the ticket, each section its `reads` cites named by path and heading, its checks and its bounds.
It quotes no section and writes nothing. `--detail full` adds the same facts as numbered steps.

## Producing the export for the `github` store

Run the pinned query from your project and hand the engine the file:

```sh
gh api graphql --paginate --slurp -F owner=<owner> -F name=<project> \
  -f query="$(cat "$(outcomebound home)/templates/tickets/github-export.graphql")" > issues.json
outcomebound tickets check --input issues.json
```

The query is shipped unedited so it can be piped straight in. Where a page or a connection
reports more than it returned, the reader says UNVERIFIED rather than guessing; a file that is not
this query's output for the declared repository is refused. Produce it again after a write of
your own. `templates/tickets/issue-template.md` is the other shipped file: the headings and the
block skeleton to copy into an issue body.
