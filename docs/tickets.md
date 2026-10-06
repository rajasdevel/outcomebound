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

To publish drafts as tickets, `outcomebound tickets publish --draft <file>…` prints the `gh`
commands. See [`publish`](#publish).

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
| `waits-on` | Optional. The decision briefs that the ticket waits on, as ids on one line separated by commas, for example `waits-on: D1, D2`. Other tickets do not wait. |

`templates/tickets/issue-template.md` is the skeleton to copy into an issue body. It has three
headings, `## Outcome`, `## Design` and `## Limits`, and the block. Only `## Outcome` and the
block are required. Keep `## Design` and `## Limits` only where they carry a decision. A ticket
names no test plan, because which tests to write is the implementer's decision.

## What the layer does, and what it never does

- **It calls no tracker.** It opens no network connection, reads no credential and writes
  nothing. Every report is about the export that it was given, and the report states the age of
  that export. For an export read from standard input, the report says that the age is unknown.
  To publish drafts, `publish` prints the `gh` commands, and `gh` runs them with the login of
  the person or agent who runs the script.
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
person. The engine reads the value in the block, not the labels: a ticket with `human-only: no`
in its block and the `human_label` applied still gets the error. The plan does not define the
check, and the brief shows it as a person's check:

```text
human-only: yes
done-when:
- signed-off: human: the release notes read correctly to the operator
```

## The verbs

Every verb takes the checkout to read. The default is `.`. Every verb except `export` takes the
export as `--input <file>`. The value `-` means standard input.

### `check`

`check [--draft <file>…] [--json]` reports what the open tickets say. It checks that each block
is well formed, that each `reads` section resolves, that each claim is defined, and that the
relations hold no cycle. The links of a closed or dropped ticket are history, and `check` does
not resolve them. `--draft` lints local draft files together, relations included, and reads no
store. On a draft run, a `blocked-by` or `parent` entry that names a published ticket, such as
`#12`, is not checked, because no store is read. `check` says so in an INFO message,
`RELATION_UNCHECKED`. `--json` prints one JSON object instead of text.

On a draft run of two or more drafts, `check` gives a WARNING about the run,
`REPEATED_GUIDANCE`, with no ticket id, for each paragraph that is in the body of every draft. The
WARNING gives the first words of the paragraph and the heading that it is under. A paragraph is
the lines between blank lines, and the comparison ignores the spaces and line breaks in it.
`check` does not compare headings, the block, or a paragraph with no letter or digit, such as a rule. It also does not compare a paragraph of the issue
template (`templates/tickets/issue-template.md`), because that text is a placeholder that the
draft kept from the template. No number of drafts and no length of a paragraph is part of the
condition. Thus, a short paragraph such as `None.` under `## Limits` in every draft also gets the
WARNING: a section that carries no decision is not written. Process guidance that every ticket
repeats is said one time, in the tickets fragment or in the project's own instructions. A
behaviour that each ticket must meet is not guidance: keep it, or move it to a contract section
that each ticket names in `reads`. The WARNING says which to do for each kind.

A claim can declare the paths that it needs, as `required_paths` in the plan. When a ticket's
claim declares a path that the ticket's `bounds` do not cover, `check` gives a WARNING,
`CLAIM_READS_OUTSIDE_BOUNDS`. A finding in that path is one that the ticket's work may not
repair. Widen `bounds`, or put a ticket that repairs it first in `blocked-by`. A claim that
declares no paths is not examined, because the plan does not say what its command reads.
When a declared path is not in the checkout as it resolves from the plan's `cwd`, but is in the
checkout as it resolves from the checkout root, `check` gives a WARNING about the plan,
`CLAIM_PATH_ABSENT`, with no ticket id. A run of that claim reads `UNVERIFIED`. When a declared
path is in neither place, it is a planned path, for example a test file that an open ticket
adds. `check` and `adopt` give no warning for a planned path, because it does not show that the
`cwd` is wrong. A run of that claim reads `UNVERIFIED` and names the path until the path exists.
When the plan's claims run in the folder of the plan file, and that folder is not the
checkout root, `check` gives a WARNING about the plan, `CLAIM_CWD_PLAN_FOLDER`, with no ticket id.
This warning does not need `required_paths`. A plan below the root runs its claims in its own folder
when it has no `cwd` or has `"cwd": "."`, because a relative `cwd` starts at the folder of the plan
file. The usual cause of both warnings is a plan in `.outcomebound/` that was written for 1.0.0, when
a relative `cwd` started at the checkout root. To run the claims at the checkout root from
`.outcomebound/`, write `"cwd": ".."`. The next step of each warning gives this `cwd`. `adopt` gives
the same two warnings at each install and upgrade, for the plan that `.outcomebound/tickets.json`
declares. It does not change the plan.

In text, the warnings for claims that the plan does not define yet (`CLAIM_PLANNED`) are one
row after the other findings. The row gives their number and their tickets. `--json` lists each
claim on its ticket.

`check` exits with `0` for PASS. It exits with `1` for FAIL or a refusal. It exits with `2` for
UNVERIFIED, a planning error or a usage error.

### `brief`

`brief <ticket> [--draft <file>…] [--detail full]` prints the document that an implementer
receives. For the `github` store, `<ticket>` is `#20` or the number alone, `20`, which a shell
does not read as a comment. `<ticket>` can also be `<owner>/<name>#20`, the form that the tracker
writes. When `<owner>/<name>` is the `repo` of the declaration (the tracker compares names without
case), it is `#20`. When it is a different repository, `brief` refuses with `TICKET_NOT_FOUND` and
names the two repositories. When the export does not hold the ticket, `TICKET_NOT_FOUND` names the
export, the time that it was written, its age, and the lowest and the highest issue number that it
holds. A ticket that is newer than the export needs a new export. `brief` does not refuse an export
because of its age. The document holds the ticket, each section that its `reads` cite (named by path and
heading, or by path alone for a whole file), its checks and its bounds. It quotes no section and writes nothing. `--detail full`
adds a `## Steps` section after `## Bounds`. It gives the same facts as numbered steps, each with
its exact command.

`brief` exits with `0` when it printed the brief. It exits with `1` for a refusal. It exits with
`2` for a planning error or a usage error.

### `publish`

`publish --draft <file>…` prints a POSIX shell script that publishes the drafts as tickets with
`gh`. It runs nothing and writes nothing. First it runs `check --draft` on all the drafts, and
it refuses with `PUBLISH_REFUSED` if `check` reports an error. The script:

- creates the issues in an order where each draft comes after each sibling draft that it names in
  `blocked-by`, `parent` or `discovered-from`;
- gives each issue its relations as `gh issue create --parent` and `--blocked-by`, with the new
  number of a sibling draft, or the number or URL of a published ticket;
- writes each body as the draft without its `# <title>` line and without the `blocked-by` and
  `parent` lines of its block, which the tracker holds. A `discovered-from` that names a sibling
  draft becomes the issue number of that draft;
- applies the declared label, and also `human_label` for `human-only: yes` or `request_label`
  for `human-only: requested`.

The header of the script names the `writes` grant of the declaration. An agent runs the script
only where that grant allows. Without a grant, a person reviews the script and runs it. A name of
a sibling draft in the prose of a body is not changed, because a word is not always a reference
to a draft. After the script runs, make a new export and run `check` on it.

The script stops at the first command that fails. The issues that it made before that command
stay in the tracker, and the script prints each one as `<draft> -> #<number>`. Do not run the
same script again, because it makes those issues a second time. To continue, make a new export.
In the drafts that are not published yet, change each name of a published sibling to its
`#<number>`. Then run `publish` again with only those drafts.

These steps stay manual:

- Create the three labels once, when a person chooses the store. The `slice-tickets` skill gives
  the three `gh label create` commands.
- To change what an accepted ticket asks, get the word of a person who can accept it, in a
  comment. An edit does not lapse the label, and the tracker keeps the history of each edit.
- Acceptance is the label. A standing request of a person that accepts a breakdown in advance is
  recorded where the person wrote it, for example a Follow-ups line in a goal envelope.

`publish` exits with `0` when it printed the script. It exits with `1` for a refusal. It exits
with `2` for a usage error.

### `export`

`export` prints two lines. The first line is a shell comment that gives the absolute path of the
pinned query that this install ships. The second line is the `gh` command that writes the export
of the declared repository to `issues.json`. `export` runs nothing and writes nothing, because
the engine holds no credential: the command runs `gh` under the login of the person or the agent
that runs it. `export` does not take `--input`. Example, for a declaration whose `repo` is
`owner/name`:

```text
$ outcomebound tickets export
# the pinned query: <outcomebound home>/templates/tickets/github-export.graphql
gh api graphql --paginate --slurp -F owner=owner -F name=name -F query=@<outcomebound home>/templates/tickets/github-export.graphql > issues.json
```

`export` exits with `0` when it printed the command. It exits with `1` for a refusal: no
declaration, or a declaration that is not valid. It exits with `2` for a usage error.

## Producing the export for the `github` store

Run the pinned query from your project, and give the engine the file:

```sh
gh api graphql --paginate --slurp -F owner=<owner> -F name=<project> \
  -f query="$(cat "$(outcomebound home)/templates/tickets/github-export.graphql")" > issues.json
outcomebound tickets check --input issues.json
```

`outcomebound tickets export` prints this command with the owner and the name of the declared
repository. It gives `gh` the query as a file (`-F query=@<path>`), so the same line runs in a
POSIX shell, PowerShell and Git Bash. `check` and `brief` read an export saved as UTF-16 with a
byte-order mark, which Windows PowerShell 5.1 documents for `>`, and one saved as UTF-8 with one. When you run `check` or `brief` without `--input`, the refusal
`INPUT_REQUIRED` prints the same command. The `input:` line of the `check` report gives the path of the export, the time
that it was written, its age, and the lowest and the highest issue number that it holds, for
example `input: issues.json; modified 2026-09-20T09:00:00Z; age 120s; holds #1 to #42`. The query is shipped unedited,
so you can pipe it straight in. The engine refuses a file that is
not the output of this query for the declared repository. Where a page or a connection reports
more than it returned, the reader says UNVERIFIED. It does not guess. Make a new export after you
change a ticket yourself.
