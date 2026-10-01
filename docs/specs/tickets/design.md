---
name: tickets
status: ratified
---

# Tickets — design

## Outcome

Work too large for one acceptance is cut into tickets a person accepts in one reading. Each
ticket states its outcome, what its implementer cannot find in the tree, the paths it may write,
and the checks that prove it done; the implementer owns how the work is carried, and the
project's own gate decides done where the work lands. The layer is opt-in and inert until
`.outcomebound/tickets.json` declares a store. How: `outcomebound tickets --help` (`check` and
`brief`), the `tickets*.py` modules, the `tickets` fragment, and the `slice-tickets` skill, which
selecting the fragment installs.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| The one store is `github`, an issue tracker read from an export; a ticket is an issue body plus one block whose decision keys are `bounds`, `human-only` and `done-when`, and optionally `reads` and `discovered-from`, while status, assignee, `blocked-by` and `parent` come from the tracker | a `files` store kept in the repository, with its own compaction of closed tickets | user | decided |
| The engine reads offline, from an export passed with `--input`, and holds no credential; tracker writes are the agent's, and only where the declaration's `writes` grant allows | the engine calling the tracker itself | user | decided |
| No ticket text is executed: each `done-when` item names a claim of the project's committed claims plan; an item written `<claim>: red-first` is read as the claim alone | commands written in the ticket | agent | decided |
| Execution is the implementer's: no ticket or skill says which tests to write, when to run them, or how to carry the work. The project's own gate, its CI or Done commands, decides done where the work lands, and the handover (the pull request or a closing comment) says what changed, each check's verdict, what was decided beyond the ticket, and the follow-ups | engine verbs that post an evidence record per run (`verify`), report readiness (`ready`) or audit the tickets (`audit`); a four-line closing note the engine parses; and a skill prescribing the turn of working a ticket: they prescribe what strong models already do, and the skill measured no better than no skill | user | decided |
| A ticket's size follows its outcome: a large outcome stays one ticket, carried milestone by milestone, and only an edge, a decision between, or parallel work on disjoint paths splits one | a size bar from each implementer's largest clean landing, or any count or length | user | decided |
| `check` judges open tickets and drafts only; a closed ticket's links are history | judging closed tickets too | user | decided |
| A ticket links no design's decision rows | `covers` on decision rows, and verbs narrowed to a parent or a spec | user | decided |
| A body is the issue template's sections, `## Outcome`, then `## Design` and `## Limits` where they carry a decision, stating the decisions its implementer needs and no test plan; where a risk no existing check covers, one `done-when` claim the work adds names it. Its length follows its outcome, and no word limit applies | tickets written for the least capable implementer, with every symbol and test restated; a word limit on the body; a `## Tests` section naming each test (`check` reads one where a body carries it) | user | decided |
| Acceptance is the `ob-ticket` label, and no edit lapses it: only accounts with triage access can label, so the declaration names no accounts | an acceptance that lapses when the text changes | user | decided |
| No ticket waits on a person's confirmation: a fact a command can read is a command claim, and the one human judgment per plan is the person's go on the plan or goal, outside the engine. The agent writes the person's digest as decision briefs | `human:` claims confirmed ticket by ticket, and a digest drawn by `ready` | user | decided |
| `brief` names each section an implementer must read, by path, anchor and heading, and quotes none | quoting every cited section verbatim | user | decided |
| `brief --detail full` renders the same facts as numbered steps, each with its command, for an implementer less capable than the ticket's author; it stays until a comparison on the least capable tier shows whether it helps, and goes if it shows no gain. The comparison runs only on request | text addressed to one reader's tier in shared instructions | user | decided |

## Edges

A claim's command is the project's own, and the engine runs none. A branch can change the plan
and the checks a ticket names, so what decides done is the gate the project protects, never the
ticket's text; where that gate does not run a ticket's claims, the handover's verdicts are the
implementer's own report, and read as that. Several agents on one backlog read what can start
from the tracker's own relations and assignees. Changing what an accepted ticket asks takes the
word of a person who can accept it, said in a comment, since an edit does not lapse the label.

## Validation

`tests/test_tickets_*.py`, run by the `tickets-*` claims; `outcomebound tickets check` and
`brief` run against a real export without an engine error.
