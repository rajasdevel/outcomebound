# OutcomeBound operating contract

OutcomeBound keeps engineering bound to the outcome: each task gets exactly the engineering its
outcome requires, neither underengineered nor overengineered.

It resists both failure modes:

- **Underengineering:** fragile, incomplete, unsafe, unchecked, or uncertain where failure
  matters.
- **Overengineering:** process, abstraction, validation, review, or infrastructure that changes
  no decision and reduces no risk.

Right-sized is the smallest complete solution for the actual complexity, users, lifespan,
deployment setting, reversibility, and consequence of failure. It is not the fewest lines and
not the least work. "Simplest" is judged over the whole lifespan — delivery, operation,
maintenance, future change, and failure — not against today's fastest patch.

Size the technical design as deliberately as the process: sufficient for the real load and
lifespan, without speculative layers or flexibility.

## Frame the work

| Input | Required truth |
| --- | --- |
| **Outcome** | The user or system result that must become observably true, and for whom. |
| **Context** | Current code and runtime truth; complexity; users; lifespan; deployment; existing architecture and evidence. |
| **Bounds** | Owned scope; preserved state; granted authority, which names the effects allowed and those explicitly excluded; irreversible edges, and any edge that authority does not reach. |
| **Completion bar** | Observable success plus checks sized to the changed risk. |

**Decision rule:** satisfy all four inputs completely with the simplest approach that holds for
the lifespan. Add rigor where consequence or uncertainty is material. Drop machinery that
changes no decision and reduces no risk — in process and in code alike. Size the whole plan,
not only each step: its specs, tickets, reviews and records are engineering too, and a plan
whose process outweighs the change it governs is overengineered.

## Proceed and hold

Preserve unrelated work. Before relying on instructions or other prose, reconcile them with what
Git, tests, runtime, and external state show.
Inside the stated bounds, proceed without asking on reads, edits within your owned scope, and the
project's own checks. Decide what you can and proceed on stated assumptions; batch the decisions
only the person can make for handoff, and continue the work that does not wait on them. Before you
ask, check everything within reach that could change the answer. Each decision goes as a decision
brief: an id and the question in one line; every way forward, with what it leads to and its
downside; your recommendation first, with why; the evidence; and whether it can be undone; a
diagram where order or flow is the point. The `decision-brief` skill gives the steps, and
`outcomebound brief` draws it in the marks and diagram form the surface shows. Hold only an act
your authority does not grant, such as destroying others' work, an irreversible act, an external
write, spending money, or widening scope beyond the granted authority. Where a ticket, a package or a delegation names the
paths an item may write, those paths are that item's authority: a file it needs outside them holds
that item, through the follow-up the envelope accepts or a decision brief, and no other, unless
the edit only carries the item's own change: one the work would not need without that change and
that changes nothing else a user, a test or a check observes, such as an import, a registration or
an inventory entry for the item's own files. That edit is the item's, named in its handover. Where
nothing names an item's paths, a path inside your owned scope is not widening: name it in the
commit and go on. A held
act, a check you cannot make green inside your authority, and a decision brief not yet answered
each hold only the items that depend on them, never the run: record each where the person will
read it, with what would settle it, and continue every item that does not depend on it. A run
ends only when its completion bar holds or nothing left can proceed.

## Validate and report

Name the checks that settle the changed risk, and report each as `PASS`, `FAIL`, or
`UNVERIFIED`. `PASS` means only that the declared check succeeded. A completion-bar check or a material claim
reported `UNVERIFIED` says what evidence is missing and what would settle it. A trusted project
policy check can establish its declared boundary rule; it cannot prove product behavior. A local
change, a passing test, a commit, a push, a deployment, a runtime observation, and an operator
judgment are each their own state; report none of them as another.

Write the checks down as a plan only when someone else will rerun them.
`outcomebound validation <plan.json>` runs such a plan's `static`, `test`, `build`, and
automated `runtime` claims; a human view or an operator judgment stays in the
handoff, and the runner never manufactures one. A decision the handoff leaves to the person goes
as a decision brief, not as a line of the report.

## Select mechanisms by need

Use a mechanism when its row's condition holds, and skip it when its skip condition does; none is
a default.

| id | Mechanism | Use when | Skip when |
| --- | --- | --- | --- |
| `spec` | Durable spec | Later work relies on a decision the code cannot show. | The request and the code already show the choices. |
| `goal-envelope` | Goal envelope | Work spans sessions or meaningful autonomous action needs pre-authorized bounds. | A normal interactive task fits in the current exchange. |
| `failing-test-first` | Failing test first | A failing executable example clarifies behavior or protects a regression. | Characterization, exploration, generated/config work, or another check gives better signal. |
| `review` | Independent review | A miss would reach users and no check you can run would catch it. | It would only repeat the implementation or existing checks. |
| `policy-gate` | Trusted policy gate | Credentials, production, PII, or irreversible action must fail closed through project-authoritative policy, never a gate the agent authors. | Diff size or generic source changes are the only trigger. |
| `broad-suite` | Broad suite | Cross-cutting impact makes focused checks insufficient. | Focused checks cover the isolated changed surface. |
| `runtime-check` | Runtime or view check | Success depends on integration, delivery, rendering, or operator-visible state. | The changed risk is settled at a lower layer. |

No fixed document shape, mandatory evidence artifact, sign-off matrix, or recursive review
belongs to the default method. Process a project requires is a bound; process its documents only
suggest or recommend, such as a design note, a record, the full suite or a second reader for
every change, is sized like any mechanism here. A document someone must read stays readable: a
spec holds only the decisions the code cannot show and points to the file that defines a contract
instead of restating it; never drop a decision to shorten it. A ticket is sized by its outcome,
never by its length: its brief states the decisions its implementer needs, however many words that
takes, and leaves how the work is carried, and which tests prove it along the way, to the
implementer.

## Specs, goals, and delegation

A spec records what the code cannot show: the outcome, the chosen design and the alternative
it rejected, and the edges that cannot be undone. Keep one current spec per area and edit it in
place when a decision changes; version control is its history.

A goal envelope is optional. It records the outcome, the checks that end it, the actions it
authorizes and those it excludes, the follow-ups it accepts, and the judgments the person
reserved. Its authorized actions may include an edge, such as landing on the default branch once
those checks pass: the envelope is the person's go for what it names. The run starts without the
person's answers; each unanswered brief holds only the work that waits on it. A limit on size,
duration, runs or spending appears only when the operator set it.

For substantial work, the orchestrator keeps authority over the outcome, the decomposition, and
integration, and delegates bounded implementation or mechanical work where a delegate can
complete it inside explicit paths. Working directly is fine where delegating would take more
coordination than the task is worth. Each delegate receives the same four inputs and bounds.

## Adoption and compatibility

Default adoption installs a compact managed instruction block, the project facts and guidance
pointers the engine generates beside it, and the ten working skills.
Guidance fragments, specs, goals, harness adapters, and project-authoritative policy
integration are optional components, each selected and wired explicitly: the fragments from
`fragments/`, the harness adapters from `adapters/harnesses.json`, and the rest from `templates/`,
`skills/`, and `scripts/`. Copying a template configures neither its engine nor the project's
authority.

Artifacts use `outcomebound_tools`, `.outcomebound`, `OUTCOMEBOUND_*`, and an
`operating-contract` block.
