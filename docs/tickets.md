# The ticket layer

Use this layer when you cut large work into tickets that a person accepts, and you want a check
that each ticket is well formed. `outcomebound tickets` reads a project's tickets from a tracker
export and reports what they say. It also prints the brief that an implementer receives.

The layer is optional. It does nothing until the project declares a store. With no
`.outcomebound/tickets.json`, every verb refuses. Nothing in OutcomeBound writes that file for
you. The flags of each verb are in its `--help`.

## Set it up

1. [Declare the store](#declaring-a-store) in `.outcomebound/tickets.json`.
2. Add the `tickets` fragment to the `--fragments` of `outcomebound adopt`. It installs the
   `slice-tickets` and `hand-off-tickets` skills.
3. [Produce an export](#producing-the-export-for-the-github-store) of your issues.
4. Run `outcomebound tickets check --input issues.json`.
5. Run `outcomebound tickets brief --input issues.json <ticket>` to see what an implementer
   receives.

Before you publish tickets, you can check drafts that are only files:
`outcomebound tickets check --draft <file>…`. This reads no store, but it still needs the
declaration. Without it, the verb refuses with `DECLARATION_MISSING`.

## What a ticket is

A ticket is an issue that carries the declared label. It has a title, a brief, and one managed
block, `id=ticket v=1`. The block holds these keys:

| Key | Meaning |
| --- | --- |
| `reads` | The sections of the tree that the implementer must read, each written `<path>#<anchor>`. A path with no anchor names the whole file. It can be empty. |
| `bounds` | The paths that the work may write. A folder is written `src`, `src/` or `src/**`. An empty value grants no path. |
| `human-only` | Whether a person must do the ticket: `yes` (a person must), `requested` (an agent asks for a person) or `no`. |
| `done-when` | The checks that say the ticket is done. Each item names one claim. |
| `discovered-from` | Optional. The ticket or issue during which this one was found. |
| `waits-on` | Optional. The decision briefs that the ticket waits on, as ids on one line separated by commas, for example `waits-on: D82, D83`. Other tickets do not wait. |

`templates/tickets/issue-template.md` is the skeleton to copy into an issue body. It has three
headings, `## Outcome`, `## Design` and `## Limits`, and the block. Only `## Outcome` and the
block are required. Keep `## Design` and `## Limits` only where they carry a decision. A ticket
names no test plan, because which tests to write is the implementer's decision.

## What the layer does, and what it never does

- **It calls no tracker.** It opens no network connection, reads no credential and writes
  nothing. Every report is about the export that it was given, and the report states the age of
  that export. For an export read from standard input, the report says that the age is unknown.
- **It runs nothing.** A `done-when` item names a claim of the committed claims plan. The
  project's own gate runs the claim where the work lands.
- **It shapes the hand-off to the implementer.** A ticket is the same whoever builds it. A
  capable implementer decides which tests to write, when to run them and how to carry the work.
  A less capable implementer receives more of these decisions already made. A small model
  receives failing tests and stubs. The `hand-off-tickets` skill describes the three tiers.
- **It leaves the handover to the implementer.** The handover is the pull request or a closing
  comment. It says what changed, the verdict of each check, what the implementer decided beyond
  the ticket, and the follow-ups that it found.

## Declaring a store

`.outcomebound/tickets.json` is one JSON object. Its schema is
`schemas/ticket-store.schema.json`.

```json
{"version": 1, "store": "github", "repo": "owner/project",
 "label": "ob-ticket", "human_label": "human-only", "request_label": "human-requested",
 "claims": ".outcomebound/ticket-claims.json"}
```

- `label` is the gate and the acceptance. An issue is a ticket when it carries this label, and no
  later edit removes that status. Only accounts with triage access can apply a label, so the
  declaration names no accounts.
- `human_label` is a person's hold on a ticket. `request_label` is an agent that asks for a
  person.
- `default_branch` is accepted, and no verb reads it.
- `writes` records a grant to write to the tracker:
  `"writes": {"granted_by": "<username>", "on": "<date>"}`. The tracker's operator gives this
  grant. Without it, an agent prints the tracker commands and a person runs them.
- `claims` names one v1 validation plan that is committed in the repository, so all claim names
  are in one namespace. The plan's format is `schemas/validation-plan.schema.json`. A relative
  `cwd` in the plan starts at the folder of the plan file, as `outcomebound validation` reads
  it. Thus a plan at `.outcomebound/ticket-claims.json` writes `"cwd": ".."` to run its claims
  at the root of the checkout. Without `cwd`, the claims run in `.outcomebound/`.

A ticket's `done-when` names claims from that plan:

```text
done-when:
- tickets-report-contract
- tickets-docs
```

Each item names one claim. An item written `<claim>: red-first` is read as the claim alone. No
ticket waits for a person to confirm it. A fact that a command can read is a claim. The one human
judgment for each plan is a person's go on the plan or goal, and it happens outside the engine.
The engine refuses a `human:` item, with one exception. On a ticket that a person does, whose
block says `human-only: yes`, an item `<name>: human: <observation>` names the check of that
person. The plan does not define it, and the brief shows it as a person's check:

```text
human-only: yes
done-when:
- signed-off: human: the release notes read correctly to the operator
```

## The verbs

Every verb takes the checkout to read. The default is `.`. Every verb takes the export as
`--input <file>`. The value `-` means standard input.

### `check`

`check [--draft <file>…] [--json]` reports what the open tickets say. It checks that each block
is well formed, that each `reads` section resolves, that each claim is defined, and that the
relations hold no cycle. The links of a closed or dropped ticket are history, and `check` does
not resolve them. `--draft` lints local draft files together, relations included, and reads no
store. On a draft run, a `blocked-by` or `parent` entry that names a published ticket, such as
`#12`, is not checked, because no store is read. `check` says so in an INFO message,
`RELATION_UNCHECKED`. `--json` prints one JSON object instead of text.

A claim can declare the paths that it needs, as `required_paths` in the plan. When a ticket's
claim declares a path that the ticket's `bounds` do not cover, `check` gives a WARNING,
`CLAIM_READS_OUTSIDE_BOUNDS`. A finding in that path is one that the ticket's work may not
repair. Widen `bounds`, or put a ticket that repairs it first in `blocked-by`. A claim that
declares no paths is not examined, because the plan does not say what its command reads.

In text, the warnings for claims that the plan does not define yet (`CLAIM_PLANNED`) are one
row after the other findings. The row gives their number and their tickets. `--json` lists each
claim on its ticket.

`check` exits with `0` for PASS. It exits with `1` for FAIL or a refusal. It exits with `2` for
UNVERIFIED, a planning error or a usage error.

### `brief`

`brief <ticket> [--draft <file>…] [--detail full]` prints the document that an implementer
receives. For the `github` store, `<ticket>` is `#20` or the number alone, `20`, which a shell
does not read as a comment. The document holds the ticket, each section that its `reads` cite (named by path and
heading, or by path alone for a whole file), its checks and its bounds. It quotes no section and writes nothing. `--detail full`
adds a `## Steps` section after `## Bounds`. It gives the same facts as numbered steps, each with
its exact command.

`brief` exits with `0` when it printed the brief. It exits with `1` for a refusal. It exits with
`2` for a planning error or a usage error.

## Producing the export for the `github` store

Run the pinned query from your project, and give the engine the file:

```sh
gh api graphql --paginate --slurp -F owner=<owner> -F name=<project> \
  -f query="$(cat "$(outcomebound home)/templates/tickets/github-export.graphql")" > issues.json
outcomebound tickets check --input issues.json
```

The query is shipped unedited, so you can pipe it straight in. The engine refuses a file that is
not the output of this query for the declared repository. Where a page or a connection reports
more than it returned, the reader says UNVERIFIED. It does not guess. Make a new export after you
change a ticket yourself.
