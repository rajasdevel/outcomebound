---
name: slice-tickets
description: Use when breaking work into tickets in a project that declares a ticket store (`.outcomebound/tickets.json`). Decides how many tickets an outcome needs and where each seam falls, what a ticket body carries, lints the drafts with `outcomebound tickets check --draft`, and publishes what the user accepted. Not for a to-do list, and not for building a ticket that exists.
---

# Slice work into tickets

You are cutting one outcome into the tickets other implementers will build from, for the user to
accept in one reading; the engine lints their form and links, and the cut is yours to judge.

**Done when** all four hold, and your report names each ticket published and where:

1. `outcomebound tickets check --draft <every draft>` reads `PASS`, and each warning is one the
   draft means.
2. Every path, symbol and `Follow:` file a draft names is in the tree.
3. The user has read the breakdown in one message they can accept in one reading and said which tickets they accept; a follow-up
   filed under a goal envelope that accepts follow-ups needs no further reading (see Publish).
4. Each accepted ticket is in the declared store with its relations set, or, without a
   `writes` grant, its commands are printed for a person and the breakdown is reported as
   waiting on them.

**Bounds.** Drafting, linting and compiling proceed without asking. Five things go to the user:
the breakdown, for their acceptance; a missing contract the rule below leaves to them; the choice
of store; a person's own act; and which implementer will build the work, which nothing waits on.
Each holds only the work that waits on it, and the rest goes on.
Publish nothing they have not seen, except a follow-up a goal envelope they wrote accepts.
`references/github.md` holds the store brief, whose yes is the one grant of tracker writes, and
the publishing commands.

## Before the first draft

- At the start, ask which implementer will build the work, a model with its effort or a tier,
  unless the person has named one. The drafts do not wait on the answer, since the tickets are the
  same whatever it is; `hand-off-tickets` shapes what each implementer is given, and reads the
  answer from a comment on each ticket, which publishing adds.
- The verbs are `outcomebound tickets <verb>`, and `<verb> --help` lists the flags. Each refuses
  with `DECLARATION_MISSING` until `.outcomebound/tickets.json` declares a store, and with
  `CLAIMS_UNREADABLE` while the validation plan the declaration's `claims` names is missing.
- A file copied from the shipped template fails `check` as it stands: it needs `# <title>` as
  its first line, `human-only` needs `yes`, `requested` or `no`, and `done-when` needs at least
  one item. Warnings a draft means: `CLAIM_PLANNED` on a claim the ticket's own work adds,
  `DISCOVERED_FROM_ABSENT` on a published ticket a draft names, since a draft run reads no store,
  and the two an epic carries, as the epic sentence below says.
- Where tickets have closed, read the follow-ups their handovers named. Carry one only where a
  user sees its result, inside a ticket or as a commit; drop the rest, listing their titles on
  one line of the breakdown.

## The line between the spec and a ticket

A contract, schema or interface belongs in the spec when something outside the slice consumes
it: another module or ticket, a tracker, a CI step, a person reading output. What only the
slice's own code touches belongs in the ticket, and splitting a slice in two moves nothing
across that line. Where the spec lacks a contract the work needs, settle it as the
`gather-requirements` skill settles a gap: a contract a later commit can undo goes into the spec
marked assumed, and the breakdown names it as one the person may reverse. A contract where every
reading would be hard to undo, such as one others already call, goes to the person as a decision
brief; the drafts that wait on it name the brief in `waits-on`, and the rest go on. No ticket
settles or invents a contract.

## The unit

A ticket is one outcome the user accepts as a whole: a change whose end state its `done-when`
claims prove. How it is carried, in milestones, sessions, commits and tests, is its
implementer's. An outcome is one thing that becomes true, said in one sentence; results joined
only by an order of work are several. Every ticket carries the same overhead whatever its size
(context rebuilt, an acceptance, a seam, a landing or a share of one), so cut as few as the outcome allows.

**Merge.** Outcomes whose parts must agree with each other, text loaded together in one voice, a
format and the code that reads it, are one ticket however many files they span; following the
same rule is not agreeing. So are outcomes whose edits to one file must agree with each other,
and outcomes the user would accept in one reading. A file tickets touch only in passing, such as
a ledger, an index, a parity count or a status table, merges none of them: its edits are ordered,
not reconciled. A change no one would accept on its own, a step an implementer carries in
passing, rides in a ticket that touches its files, or lands as a commit. A spec that names a grain is giving an order of work; the rules here decide the cut.

**Split.** A ticket's size follows its outcome, never a count or a length: a large outcome
stays one ticket, carried milestone by milestone. A boundary falls only where one of these
holds, and the breakdown names which:

- **An edge.** An irreversible or outward act, or authority the rest of the work does not need,
  stands alone, so accepting it is its own decision. Spending an allowance the acceptance
  grants, such as its runs, is no edge.
- **A decision between.** Work that cannot be designed until the user decides something the
  earlier work reveals waits in its own ticket, `blocked-by` the earlier one. Work that waits on
  a decision already put to the person names that brief in `waits-on`, and every other ticket
  stays startable.
- **Parallel without reconciliation.** Parts with disjoint `bounds` and no shared design choice,
  which more than one implementer will actually work at the same time.

Nothing else splits a ticket: not the number of files or findings, not a module boundary, not
which change lands first, not the length of its brief, not a point where an intermediate result
could be checked. That is a milestone inside the ticket, and planning it is the implementer's.

**Shape.** A parent gathers children one level deep and exists only where they share an outcome
the user judges once they have landed; a breakdown of one ticket has no parent. Chart to the next
decision that is the user's by the `decision-brief` skill's test; what the work uncovers arrives
as follow-ups, not as a tree drawn in advance. The user's go on the breakdown is the one human
judgment the plan needs; after it, only a ticket that crosses an edge gets a look, and no ticket
waits on a person's confirmation.

## Write the ticket

Copy `$(outcomebound home)/templates/tickets/issue-template.md`; a draft opens with `# <title>`,
and its id is the file name without the extension. Write for the implementer who will take it,
and state only the decisions the tree does not show. Name by path and
symbol only what a search would not find, never by line number, and copy no existing shape from
the tree. A name the slice adds, and any text a person or a record will read, is written out
verbatim.

Three things stay out: the slice's own implementation, since code in a ticket has run against
nothing and becomes the user's text, which the implementer may not correct; a restated
contract section, which `reads` names and the implementer reads where it stands; and guidance
every ticket would repeat, which the tickets fragment says once.

Everything a brief states is decided; `Suggested order:` and `Hint:` are the two markers that
make a line advice. `## Limits` names what must not change, the acts outside the ticket's
`bounds` that come back to the person, and what the slice leaves out. Work that would cross one
leaves that part, says so in the handover, and finishes the rest; it holds no other ticket. Any
other detail that cannot hold as written is one the implementer departs from and reports.
Name no test plan: which tests to write, and when to run them, is the implementer's. Where the
outcome carries a risk no existing check covers, `done-when` names one claim the work adds for
it, and one line under `## Design` says what it must catch.

The block, filled:

```text
<!-- outcomebound:begin id=ticket v=1 -->
reads: docs/specs/export/design.md#decisions
bounds: src/export, tests/test_export.py, .outcomebound/ticket-claims.json
human-only: no
done-when:
- export-roundtrip
- export-docs
blocked-by: schema-settled
parent: #41
<!-- outcomebound:end id=ticket -->
```

- `reads` names sections as `<path>#<anchor>`; `check` reports an error for one that resolves
  to no single heading.
- `bounds` are the paths the slice may write: a path without a trailing slash, or a glob; a
  directory grants everything under it (`src/export` and `src/export/**` grant the same tree).
  Include the files its tests live in, and the claims plan where it adds a claim. Draw `bounds`
  as wide as the outcome's authority, a directory before a list of files, and disjoint only where
  tickets run in parallel: a file the work must change just outside them holds that work when
  nothing is wrong, unless the edit only carries the ticket's own change, which the tickets fragment
  leaves to the implementer. Where the project keeps an inventory that every added module must enter, such as a
  registry, a parity count, an import census or a public-surface digest, put that file in
  `bounds` all the same, so that no implementer has to judge it: the last change that added a module shows which files it touched. Where an earlier
  ticket of the same breakdown moves a mechanism into a new file, a later ticket that changes the
  mechanism names that file in its `bounds`. Empty bounds grant no path, right for a person's ticket and for a parent that only
  gathers its children.
- A `done-when` claim whose command reads more than the ticket's own paths, such as a type, lint,
  format or shell gate over the whole tree, or a runner script a suite needs, gets `bounds` that
  cover what it reads where the outcome's authority already reaches those paths; otherwise a
  repair ticket that makes that command green outside them comes first, named in `blocked-by`. A
  claim that names those paths in the plan's `required_paths` lets `check` warn,
  `CLAIM_READS_OUTSIDE_BOUNDS`, where `bounds` do not cover them.
- `human-only: yes` marks a ticket a person will do; `requested` is an agent's, never a draft's.
- A `done-when` item is a claim a command settles; a fact a command can read is one, and so is
  an agent's own act, read from the artifact it left. A judgment only the user can make is no
  claim, and `check` reports a `human:` item as an error, except on a `human-only: yes` ticket,
  where `<name>: human: <observation>` names the person's own check, which the plan does not
  define.
- `blocked-by`, `parent` and `discovered-from` name a sibling draft by its file name without the
  extension, or a published ticket by `#N`. The first two leave the block at publishing and
  become the tracker's relations; `discovered-from` stays, rewritten to the issue number.
- `waits-on` names, by its id, the decision brief whose answer the ticket's work waits on. It
  stays in the block, and `check` and `brief` show it, so a run can tell which tickets can start:
  a ticket without `waits-on` waits on no brief, whatever briefs are open.

A relation is written on the ticket that depends, pointing at what stands before it, and never
on the other side: the tracker shows the reverse. An epic is a parent with empty `bounds`,
`reads` naming the sections its children answer to, and a `done-when` over what they make true
together. Where its children build the whole of one design, its `reads` names the design (its
path, or its sections) and its `done-when` the design's `## Validation` checks, those the claims
plan holds and those a child's work adds, so the epic closing with them green says the design is
built; a check no command settles is none of them. On an epic, `CLAIM_PLANNED` and
`CLAIM_READS_OUTSIDE_BOUNDS` are warnings the draft means, since it writes nothing. A child's
`reads` names the sections it answers to, which another child may share. The epic's claims are
reported in its closing comment and hold no child.

## Lint, then show the user

Lint the whole breakdown in one run, `check --draft <file>...` with every draft, so relations
and cycles are judged across them. Then show the user the breakdown in one message they can accept in one reading: for each ticket
its outcome sentence, its `Accepting this decides:` line, the boundary that separates it from
its neighbours; then the relations, and the implementer the work is for. Where the run starts
from a goal envelope, its `Tickets:` line carries the same outcome lines. Compile any ticket they open with
`brief <id> --draft <file>...`, given every draft.

## Publish

Publish with the script `outcomebound tickets publish --draft <every accepted draft>` prints, as
`references/github.md` says: it creates each accepted ticket with the ticket label and its parent
and blocking relations, and runs nothing itself. Then comment on each ticket with the implementer
it is for, where one was named. What you find that is not this
breakdown's work is a follow-up for the next one, or, where it is a slice by the rules above, a
draft with `discovered-from` naming the ticket whose work surfaced it. A goal envelope the person
wrote whose Follow-ups line accepts follow-ups is their acceptance of each issue a run files under
it, inside the envelope's Authorized line: lint it, publish it with the ticket label and
`discovered-from`, and build it in the run as the envelope orders. Without that line, a follow-up
waits for the person's next reading, and the work that does not need it goes on. A person's own
act with no implementer work in it, a tag push or a grant commit, is not a ticket: it goes to the
person on its own and gets its own go, and where it needs preparing, the preparation is the
ticket.
