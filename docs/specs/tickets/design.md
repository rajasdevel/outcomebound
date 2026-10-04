---
name: tickets
status: ratified
---

# Tickets — design

## Outcome

Work too large for one acceptance is cut into tickets a person accepts in one reading. Each
ticket states its outcome, what its implementer cannot find in the tree, the paths it may write,
and the checks that prove it done. The layer is opt-in and inert until `.outcomebound/tickets.json`
declares a store. The invariant the layer holds: no draft reaches the publish script while
`check` reports an ERROR about it, and no ticket text runs as a command. How: `outcomebound tickets --help` (`check`, `brief` and `publish`), the `tickets*.py`
modules, the `tickets` fragment, and the `slice-tickets` and `hand-off-tickets` skills, which
selecting the fragment installs. A ticket is the same whoever builds it; what changes with the
implementer is the package the agent handing it over writes, shaped by the implementer's tier.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The one store is `github`, an issue tracker; a ticket is an issue body plus one block with decision keys `bounds`, `human-only` and `done-when`, optionally `reads` and `discovered-from`; optional `waits-on` names the decision briefs it awaits, holding no other ticket (maintainer, 2026-10-04); status, assignee, `blocked-by` and `parent` come from the tracker | a `files` store kept in the repository, with its own compaction of closed tickets | user | decided |
| The engine reads offline, from an export, and holds no credential; tracker writes are the agent's, only where the declaration's `writes` grant allows | the engine calling the tracker itself | user | decided |
| `publish` prints the `gh` script that publishes a breakdown of drafts: in an order where each relation names an issue that exists, each body without the keys the tracker holds and with a sibling's `discovered-from` as its number, the labels saying what the hold says; it runs nothing, and the script's header names the `writes` grant or says a person runs it. Creating the labels (once, on the person's yes), changing an accepted ticket (a person's word in a comment; the tracker keeps each edit) and a standing acceptance (recorded where the person wrote it) stay manual, and `INPUT_REQUIRED` prints the export command for the declared repository | a verb per tracker step that calls the tracker, which needs a credential; rewriting a sibling's name in prose, which no word decides | agent | decided |
| No ticket text is executed: each `done-when` item names a claim of the project's committed claims plan; an item written `<claim>: red-first` is read as the claim alone | commands written in the ticket | agent | decided |
| At the outcome tier, execution is the implementer's: no ticket, package or skill says which tests to write, when to run them, or how to carry the work; a design-tier package names the test each edge case needs, and a spec-tier package carries the tests themselves. The project's own gate, its CI or Done commands, decides done where the work lands, and the handover (the pull request or a closing comment) says what changed, each check's verdict, what was decided beyond the ticket, and the follow-ups | engine verbs `verify` (an evidence record per run), `ready` and `audit`; a four-line closing note the engine parses; a skill prescribing how to work a ticket: they prescribe what strong models already do, and the skill measured no better than none | user | decided |
| A ticket's size follows its outcome: a large outcome stays one ticket, carried milestone by milestone, and only an edge, a decision between, or parallel work on disjoint paths splits one | a size bar from each implementer's largest clean landing, or any count or length | user | decided |
| Before slicing, the agent asks which implementer will build the work, a model with its effort or a tier, unless the person has named one. The drafts do not wait on the answer, since the tickets are the same whatever it is; at publishing a comment on each ticket records it, and the hand-off reads it there, or, with none, names the one it launches (maintainer, 2026-10-04) | inferring the implementer; asking only at hand-off | user | decided |
| A `done-when` claim whose command reads more than the ticket's own paths (a whole-tree type, lint, format or shell gate; a runner script a suite needs) gets `bounds` that cover what it reads where the outcome's authority already reaches those paths, else a repair ticket before it in `blocked-by`, so the implementer can make it green inside `bounds` | `bounds` over the changed files only, which leaves a finding elsewhere in the tree to a scope brief at hand-off | agent | decided |
| A ticket is the acceptance unit for every implementer. At hand-off the agent handing it over writes a package for the implementer's tier: at the outcome tier the ticket alone; at the design tier the ticket plus the approach, signatures, invariants, an edge-case table naming each row's test, and milestones; at the spec tier the ticket cut into steps, each step's package written once the previous step is committed on the ticket's branch, passing, and reviewed by an outcome-tier model. The person accepts the ticket, not the package; the project's gate decides done at every tier. Where a step's package would be its code, the agent writes the code | tickets written for their target tier, so a breakdown for a small model has more and longer tickets, each accepted, and goes stale as earlier ones land | user | decided |
| Three tiers, named by what the implementer is trusted to decide: outcome, design and spec. Each tier's profile is written for the weakest model in it. A model's tier is read from a placement table keyed by model, effort and quantization, kept dated in the research repository's `applications/implementer-tiers.md`; the person may name a tier instead; a model the table lacks, or any model where neither the clone nor the public link can be read, takes the spec tier (maintainer, 2026-10-04). A tier the project's committed instructions give the model stands as the person's; where neither places it, the handover says the table does not list it and names any project rule that routes work to it | a profile per model, stale within weeks of a release; scores on several capability axes, which need measurements few models have | user | decided |
| A spec-tier step's package is executable first: tests the agent wrote and ran red for the reason they name, and stubs with exact signatures; then files, symbol shapes, algorithm and data structure, verbatim text, edge cases, and the acts that end a step (maintainer, 2026-10-04). The package's tests are fixed: the implementer adds tests and changes none of them | detailed prose alone, with the small model writing the tests: prose no run has checked, which small models follow when wrong and drop under load | user | decided |
| `check` judges open tickets and drafts only; a closed ticket's links are history | judging closed tickets too | user | decided |
| `check` warns (`CLAIM_READS_OUTSIDE_BOUNDS`) where a `done-when` claim's declared `required_paths` reach past the ticket's `bounds`, since the implementer may not repair a finding there; a claim that declares none is not judged, because the plan does not say what its command reads | UNVERIFIED for each claim that declares no paths, which would turn most runs UNVERIFIED; guessing paths from a command's arguments | agent | decided |
| A ticket links no design's decision rows | `covers` on decision rows, and verbs narrowed to a parent or a spec | user | decided |
| A body is the issue template's sections, `## Outcome`, then `## Design` and `## Limits` where they carry a decision, stating the decisions its implementer needs and no test plan; where a risk no existing check covers, one `done-when` claim the work adds names it. Its length follows its outcome, and no word limit applies | tickets written for the least capable implementer, with every symbol and test restated; a word limit on the body; a `## Tests` section naming each test (`check` reads one where a body carries it) | user | decided |
| Acceptance is the `ob-ticket` label, and no edit lapses it: only accounts with triage access can label, so the declaration names no accounts. A Follow-ups line in a goal envelope the person wrote accepts the issues a run files under it (maintainer, 2026-10-04) | an acceptance that lapses when the text changes | user | decided |
| No agent's ticket waits on a person's confirmation: a fact a command can read is a command claim, and the one human judgment per plan is the person's go on the plan or goal; a ticket a person does (`human-only: yes`) may name that person's check (#17) (maintainer, 2026-10-04). The agent writes the person's digest as decision briefs | `human:` claims confirmed ticket by ticket, and a digest drawn by `ready` | user | decided |
| A ticket a person does (`human-only: yes`) may name that person's check in `done-when` as `<name>: human: <observation>`; the plan need not define it, `brief` shows it as a person's check, and on every other ticket the item stays an error, so no agent's ticket waits on a person; it is the block's value that decides, never a label (issue #17) | a planned receipt claim on each human-only ticket, which adds a warning to every run | agent | decided |
| `brief` names each section an implementer must read, by path, anchor and heading, and quotes none; a `reads` path with no anchor names the whole file, by its path alone | quoting every cited section verbatim | user | decided |
| `brief --detail full` renders the facts as numbered steps; the spec tier's default brief by the project's choice, judged on longer work | text addressed to one reader's tier in shared instructions | user | decided |
| The hand-off ships only as far as a comparison supports it: fixtures run with the ticket alone and with its tier's package, on one implementer per tier, nine runs a cell, and a part showing no gain is cut by default. E17 (`docs/evaluations.md`, 2026-10-03): the spec package helped its implementer and did not hurt the outcome tier; the design package had no headroom; `--detail full` tied the ticket alone (6 of 9) on three small tasks, and the project keeps it (row above). It reruns before a release changing the hand-off | shipping the packages as guidance and learning from closed tickets, which cannot separate the package's effect from the model's | user | decided |

## Edges

A claim's command is the project's own, and the engine runs none. A branch can change the plan
and the checks a ticket names, so what decides done is the gate the project protects, never the
ticket's text; where that gate does not run a ticket's claims, the handover's verdicts are the
implementer's own report, and read as that. Several agents on one backlog read what can start
from the tracker's own relations and assignees. Changing what an accepted ticket asks takes the
word of a person who can accept it, said in a comment, since an edit does not lapse the label;
while it waits, the tickets that do not depend on it go on (maintainer, 2026-10-04).

What each verdict reads, and who writes it (`outcomebound_tools/tickets_*.py`). `check` and
`publish` read the tracker export given as `--input` (`tickets_store`), which whoever has access
to the tracker writes; acceptance, the ticket label the declaration names, only accounts with
triage access. Drafts
are local files the agent writes (`tickets_draft`). The declaration, `.outcomebound/tickets.json`
(`tickets_declaration`), and the claims plan it names (`tickets_claims`) are committed, so the
change under check can write them: a declaration can add its own `writes` grant, and a plan can
change the command a claim runs. Both are accepted because they are visible: they show in the
change's diff, the publish script's header names the grant or says a person runs it, and the
project's own gate decides done, as above.

## Validation

`tests/test_tickets_*.py`, run by the `tickets-*` claims; `outcomebound tickets check` and
`brief` run against a real export without an engine error; the hand-off fixtures listed in
`evals/README.md`, run before a release carries the hand-off.
