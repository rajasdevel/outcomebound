---
name: lifecycle
status: ratified
---

# Lifecycle support — design

This design recorded the cross-area decisions for v1.5.0, which shipped on 2026-10-08, and the
composable lifecycle of v1.6.0 (R12 to R17 and the section of that name). It is the current design
for lifecycle support. The requirements below are the product contracts the
release was built to; they are not claims that the release passed them. The qualification
record, [E21](../../evaluations.md#e21-direct-skill-and-lifecycle-qualification), and the
v1.5.0 changelog section say what was observed and what stayed `UNVERIFIED`.

## Outcome

An adopting project can carry an idea through the applicable stages to a high quality result,
keep its requirements and authority intact at each handoff, and see the evidence for delivery,
operation and eventual retirement. The route fits the project's users, risk and lifespan.
OutcomeBound supplies skills, bounds, guidance, tools and quality controls where they change a
decision or catch a material failure. It does not impose every stage on every change.

From 1.6.0 the lifecycle is composable. Each project keeps its own route: a client delivery, a
solo maintainer's package, an internal system and a prototype each work in their own way.
OutcomeBound adapts to the route at adoption, supports each stage the route has, and carries the
project through a change from one lifecycle to another: a prototype gains outside users, a solo
project gains a maintainer, a client contract starts or ends, or the owner changes the route.

## Requirements

R1. Support the full applicable lifecycle: idea and discovery, requirements, design, accepted work, implementation, validation, review and landing, release, deployment, operation, incident and feedback, maintenance and retirement.
R2. At each applicable transition, identify the input, output, owner of the next action, authority, completion evidence and when the transition can be skipped.
R3. Preserve source requirements through design and tickets; distinguish source accounting, requirement mapping and evidence that the result meets the requirement.
R4. Make evaluation evidence reliable before it is used to justify instruction changes; correct the confirmed defects in [issue #95](https://github.com/rajasdevel/outcomebound/issues/95).
R5. [assumed] Identify direct behavior coverage for every shipped skill; add or rerun missing and affected cases, reuse valid unchanged evidence, and check useful behavior retained from inspirations.
R6. Preserve project-owned work through adoption and make native skill persistence, loading and hook execution separate observable claims.
R7. Target v1.5.0 for all known in-scope defects and justified improvements; resolve valid failures before release rather than rename them as missing evidence.
R8. Keep supported install and command contracts compatible, preserve project gates, and qualify the exact release tree before publication and downstream adoption.
R9. Include security, privacy, accessibility, reliability, performance, compatibility and recovery where the project's outcome or changed risk requires them.
R10. When this work establishes a new general lesson, return it to research through the existing contribution route. Otherwise retain the existing research. Keep product evaluation results in this repository.
R11. Keep hook installation and execution portable with no unnecessary external tooling; distinguish the engine runtime from a project's genuine check dependencies and make missing setup explicit without weakening checks.
R12. Adapt to the project's own lifecycle at adoption: record what the project does now, with the source of each fact, and offer the nearest shipped template only as a comparison.
R13. Select the obligations of each stream of work from a few exposure facts (who can be hurt, who accepts the work, which acts cannot be undone, the expected life, who maintains it, and how much of the work agents write against the review capacity), never from a count of lines, files, commits or users.
R14. Keep one copy of each route: the project's own document. OutcomeBound points to it and does not restate its stages.
R15. Support each stage a route can have: intake from sources and trackers, definition, design, slicing, build, review and landing, acceptance by an outside party, release, verification, operation, maintenance and retirement.
R16. Treat a change of exposure or of route as a transition the person decides, with the obligations that turn on and off, the work in flight and what it now owes, and what the change invalidates. Nothing switches by itself.
R17. Report where the project's files show a fact that its recorded exposure contradicts, without refusing anything.

The maintainer's request of 2026-10-09 supplied R12 to R17. The release goal supplied R1, R7 and R11. R2–R6 and R8–R10 are the design's interpretation of
complete lifecycle support and the existing contract; none is a new grant. The shipped
lifecycle reference, skills, install and release checks, and E21 hold R2–R4, R6 and R8–R10.
R5 stays `[assumed]`: E21 identifies a direct case for every shipped skill, but no record
checks the behavior kept from each cited inspiration, and E21 claims no parity with any.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| v1.5.0 is the target for the complete known scope; a validated defect or justified improvement found while carrying it out joins that scope | scheduling known work across further releases merely to make this release smaller | user | decided |
| Full support means a usable, checked route across every applicable transition; stage names do not by themselves justify skills, tools, records or approvals | a mandatory sequence or a separate skill for every stage | agent | decided |
| The lifecycle route belongs in an on-demand reference of `using-outcomebound`, installed with that skill; the human guide links to it. The core entrypoint routes there only when a task needs coordination across stages or delivery has stopped before its outcome | a repository-only guide that installed agents cannot find; expanding the always-loaded kernel | agent | decided |
| Existing area designs keep ownership of their contracts. This design owns transition coverage and release evidence, not copies of wire formats or engine behavior | a second master specification that repeats each area's decisions | agent | decided |
| Risk dimensions are selected from the outcome and changed surface. A small local change needs no service owner or operational exercise; a service change cannot omit applicable security, privacy, accessibility, capacity or recovery questions merely because unit tests pass | a universal audit checklist; a claim that the quality floor proves product quality | agent | decided |
| Requirements-to-ticket mapping stays optional in the general engine. This release's source-driven breakdown uses `satisfies` and a semantic review; an id proves accounting only | a new refusal or a requirement-id list treated as proof of implementation | agent | decided |
| Known grader defects are repaired before candidate behavior is judged. An unreadable or denied effect remains UNVERIFIED; an observed wrong effect is FAIL | counting an attempted command as an effect; hiding a behavior failure by broadening a grader | agent | decided |
| Qualification uses a deterministic floor, direct skill and transition scenarios, independent cases, and real adoption. It makes bounded claims, not a promise about every future task or every model | universal proof; shipping known valid in-scope failures and waiting for field reports | agent | assumed |
| A new skill must have a distinct trigger and an unserved repeatable decision. A case first runs against current guidance; a missing reference, tool check or narrow clause is preferred when it resolves the failure | an operations, retirement, security or architecture skill selected from its stage name alone | agent | decided |
| A native harness claim needs a native observation with the installed bytes and environment identified. Tests of the engine or an isolated evaluation runner do not establish hook events or skill discovery | inferring native execution from a configuration file or a successful direct invocation | agent | decided |
| Research provides dated evidence and alternatives. Product-specific changes and results stay here; a new general finding is prepared for the existing research contribution path | editing the shared research clone or publishing an anecdote as a general rule | agent | decided |
| The lifecycle is composable: a core that every lifecycle shares (the kernel, the transition table, the skills); exposure facts for each stream of work; obligations that the exposure facts select; and the project's own routes. A template is a starting comparison, never an install | one static route for every project; a route chosen per repository when one repository holds several streams | user | decided |
| The exposure facts, each stream's route document, the gate owners, the leave-when signals, the project's measure of a better outcome and the dated changes are lines in the project's `local` fragment, which every task already loads | a separate lifecycle file with stage tables and a form check, which copies routes the project already writes down and checks only a model's own text | agent | decided |
| Obligations are fragments. The adopt skill proposes them from the exposure facts and the signals, and the person confirms; two setup fragments are new: `client` (acceptance by an outside party) and `explore` (work whose aim is to learn) | a closed list of duty ids beside the fragments, which gives one text two selectors | agent | decided |
| A person decides only at an irreversible edge, an outside contract or an unsettled intent; a step inside a unit of work is not a gate | a gate at every stage; a gate named by the stage alone | agent | decided |
| A transition is a change of exposure or of route. Its decision brief carries the fragment diff, the work in flight read from the ticket export, the worktrees, the open briefs, the standing grants and any partial deploy, what each item now owes, and what the change invalidates; on a yes, only the stages not yet reached are planned again | automatic switching; restarting the work in flight under the new route | agent | decided |
| Three templates, `personal`, `shared` and `client`, use the new-project reference's words. Each holds example `local` lines, a fragment list, a fits-when line, and leave-when rows that include the moves back | five templates on two axes; a template per kind of company | agent | decided |
| `land-change`, `run-acceptance` and `sync-tracker` ship in 1.6.0, before a case has run against the text they replace; the ten-skill default install becomes thirteen (maintainer, 2026-10-10) | stage support as text only, with skills after fixtures show that the text does not resolve the case | user | decided |
| `adopt --check` and `--detect` print one line for each signal a file shows that the recorded exposure or fragment selection contradicts, refuse nothing and change no exit code | no check until a fixture shows that the exposure lines change an agent's choice; a form check of the record | agent | decided |

The qualification row stays `assumed`. E21 uses synthetic adoption fixtures and the engine's
own checks. No record in this repository shows the release adopted by a real project, so that
part of the row has no evidence here.

## Composable lifecycle

**The core** is the same in every lifecycle: the kernel's four inputs, the transition table below,
and the working skills, each a practice that works in every route.

**Exposure.** The `local` fragment's Context holds one `Exposure —` line, or one for each stream
where the streams differ; the project's facts are their union. The facts: who can be hurt; who
accepts the work; which acts cannot be undone; the expected life (to learn, then discard; to learn,
then keep what the signal justifies, with the sacrificial parts named; or the life of a product);
who maintains it; and how much of the work agents write against the review capacity. Each fact is
marked `confirmed`, `observed <file>` or `assumed`.

**Obligations are fragments.** The adopt skill proposes them from the exposure facts and the
signals:

| Exposure | Fragment, with what 1.6.0 adds to it |
| --- | --- |
| two or more maintainers, or required review | `team`, and review capacity matched to the volume agents change |
| one maintainer | `solo`, and an end date for each standing grant |
| it deploys a service | `deploy` (the gate chain, several changes on one build, the emergency path, the results Successful, Failed and Inconclusive, the closing note, production data kept apart from test data) and `runtime` |
| it publishes a package | `ci-release`, and consumers moved within a stated window or the hold recorded with an owner |
| it changes stored data | `db-migrations` |
| a client or a regulator accepts the work | `client` (new) |
| its expected life starts with learning | `explore` (new) |

**Routes stay the project's.** Context names each stream's route document and the kind of change
that takes it (`Streams — <stream>: route in <file>; takes <kind of change>`). Bounds names each
gate's owner and evidence (`Gates — <gate>: owner <role>, evidence <kind>`). Distinguish holds the
project's own ladder of states. Where a stream has no written route, the adopt skill proposes the
lines for the project's own document, each with the file or commit that shows it. Paths by kind of
change are the kernel's sizing applied to each change.

**Better means.** One Context line holds the project's own measure of a better outcome, in its
words. The misfit report, the stop-or-pivot brief of `explore` and the transition brief judge
against it.

**Leave when.** Bounds lines name each signal that ends the current lifecycle, where it can be
observed (a file pattern, a tracker field, or the person's word) and who watches it, with the
fragment diff it would propose. Moves back are normal rows, and a project may strike a row with its
reason. The agent checks these lines at adoption and at each handoff; the drift lines read the
signals that files show.

**A transition** is a change of exposure or of route: a fact moves, the person gives a directive, a
stream starts or ends, the authority model changes, a leave-when signal appears, or a drift line
prints. The agent writes one decision brief with the fragment diff and the work in flight (open
tickets from the export, worktrees with uncommitted work, open briefs, standing grants and their
dates, a deploy or cutover receipt in a partial phase), what each item now owes, what the change
invalidates and what to retire. On a yes it adds a dated `Changed —` line to Context, and plans only
the stages not yet reached. Each item in flight keeps the state its own record shows.

**Templates.** `templates/lifecycle/personal.md`, `shared.md` and `client.md` take the new-project
reference's words. A throwaway item needs no template; regulated work is `shared` with the
new-project reference's brief for each compliance choice. The adopt skill offers the nearest one as
a comparison and names the differences; adoption never installs one.

**Stage support.** `land-change` drives a request and its fix loop to landing; `run-acceptance`
prepares, pre-runs and records acceptance by an outside party; `sync-tracker` reads a tracker that
is not the ticket store into a markdown source (the sources design reads markdown) and writes back
batched comments under a grant, each other write being a decision brief. The `gather-requirements`
reference names the source kinds (a transcript, a data trace, a story, a design file). A held
decision brief names its default and its expiry, so the work that waits on it can go on.

**Drift.** `adopt --detect` reads two more signals: the authors in the recent history, and tags or
a version file. `adopt --check` and `--detect` compare the signals with the recorded exposure and
fragment selection and print `signal present, record says otherwise` lines.

## Transition coverage

| Transition | Existing owner | v1.5.0 completion evidence |
| --- | --- | --- |
| Idea to framed outcome | `gather-requirements`, `using-outcomebound` and, from 1.6.0, its new-project reference, decision support | A bounded ambiguous request becomes a clear outcome, assumptions and reserved decisions, without unnecessary questions or ceremony. The new-project reference has no run yet: what it does for an idea with no repository is `UNVERIFIED`. |
| Sources to requirements | sources design, `gather-requirements`; from 1.6.0, `sync-tracker` for a tracker that is not the ticket store | Requirements retain their constraints, provenance and correction history; visual requirements retain unshown states and unresolved comparisons. |
| Requirements to design | contract's spec mechanism, `explain-spec` | The design settles downstream choices and material quality dimensions; explanation names gaps without claiming a person's understanding. |
| Design to accepted work | tickets design, `slice-tickets` | The breakdown covers the accepted outcome without inflating ticket count; source mappings and semantic review agree. |
| Accepted work to implementation | `hand-off-tickets`, multi-agent and workspace guidance | A direct handoff preserves scope and authority, provides only the required package, and uses current artifacts. |
| Implementation to validation | `tests-worth-keeping`, floor, validation and runtime guidance | Tests catch the named risk; runtime evidence covers the changed path; missing tools and pre-existing failures are reported accurately. |
| Review to landing | `review-findings`, review design, project gate; from 1.6.0, `land-change` for the request and its fix loop | Findings have checked dispositions and the exact landing uses the project's gate. |
| Acceptance by an outside party | from 1.6.0, `run-acceptance` and the `client` fragment | The acceptance names the build and the person; the agent's own pre-run is not acceptance; only an accepted build is promoted. No run yet: `UNVERIFIED`. |
| Landing to release and deploy | distribution design, CI release and deploy guidance | Built, published, deployed and observed identities remain distinct; indirect effects and recovery stay inside authority. |
| Delivery to operation | deploy, runtime and commands guidance | A finite observation requirement, operator, response route, recovery limits and unavailable telemetry are handled without starting an ungranted ongoing job. |
| Incident and feedback to maintenance | `diagnose`, requirements and research guidance | Evidence separates cause, symptom, correction and recurrence; a defect or changed outcome returns to the appropriate stage. |
| A change of lifecycle | from 1.6.0, the lifecycle reference's transitions section, `decision-brief`, and the drift lines of `adopt --check` | The brief names the fragment diff, the work in flight and what each item owes; nothing switches without the person. One fixture pair tests it (Validation). |
| Maintenance to retirement | contract, deploy and database migration guidance | Consumer and retention conditions are checked, authorized preparation continues, and removal waits for its actual gate and grant. |

## Area updates

| Work | Authoritative design or record |
| --- | --- |
| Evaluation outcomes, fixture contracts, skill coverage and behavior evidence | [skills](../skills/design.md), `evals/README.md`, `docs/evaluations.md` |
| Provenance and semantic coverage limits | [sources](../sources/design.md), [tickets](../tickets/design.md) |
| Portable adoption and native surfaces | [install](../install/design.md) |
| Native prompt, Stop and retry observations | [finish-check](../finish-check/design.md) |
| Release identity, packaging and publication | [distribution](../distribution/design.md), `docs/VERSIONING.md` |
| General lessons and product-specific evaluation records | [research](../research/design.md) |

An adopter's own defect stays in that project's design or ticket. It changes an OutcomeBound
design only when a synthetic reproduction establishes a shared installation, guidance or tool
defect. A local release work record tracks those repairs without publishing adopter details.

## Validation

Use the current tools and evidence records. This work added no new qualification framework,
evidence schema, runtime ledger or model-judge service.

1. Repair the graders with deterministic valid and adverse examples in the existing scenario,
   adapter and runner tests. These checks run no model.
2. Map every skill to its existing direct case and actual evidence. Reuse unchanged records only
   where their instruction, fixture, tools and grader inputs support the current claim. Use the
   direct handoff and adoption cases and the specific controls that expose a gap.
3. Run a small named pilot of affected cases. Inspect outcomes and traces before changing
   instructions. Use an independent case for a substantive repair and one reusable no-work
   control where it serves the claim. Compare the old and proposed text with equal tools; when
   a material difference from an inspiration remains uncertain, compare its pinned text too.
4. Use one local lifecycle example with operation and retirement branches to test the handoffs.
   Bound time and effects; include unavailable telemetry and a consumer that still needs data.
   Its small-task control must skip unnecessary stages. This is integration evidence, not
   proof of each skill's isolated benefit.
5. Extend the existing install, skill-path and package checks for the lifecycle reference and
   ignored native files. Include a minimal install without optional fragments or an engine
   checkout/launcher. A machine-local install need not commit its files.
6. Observe prompt/Stop/retry in one declared native environment for each implemented hook row,
   `claude-code` and `codex`. A short record names identity, events, result and limits.
   Other platform combinations retain their own observed or UNVERIFIED status.
7. Apply the existing landing and release sequence: gate, floor, suite, scrub, required canary
   and release-check on the required tree. A model pass is not added to normal CI.

For 1.6.0, four further obligations hold. The engine's new signals and drift lines have tests
with a project whose files contradict its record and one whose files agree. Each new fragment and
skill passes the instruction, frontmatter and skill-path checks, and the canary runs before the
adopt change lands. Each shipped template is read against four projects of different kinds, and a
line that changes no decision in the next month of that project's work is cut. One fixture pair
runs on one model, one run per arm, the new text against the text before it: a small change in a
client-delivery repository takes its light route, and a prototype's first invited user, or a change
of route by the owner's word, produces a brief with the fragment diff and the work in flight.

One qualification table in the existing evaluation record links the cases, candidate identity,
verdicts and limitations to the runner's files and native observations. Review the actual
outcomes before closing the work. A model-call or summary exit code is not a behavior verdict.
These obligations remain required even though no new aggregate gate was built.

All known valid in-scope failures must be fixed and checked before release. Missing required
evidence cannot pass through documentation or a waiver. General skill superiority, every model
and every platform are not claims this bounded qualification establishes. Post-release feedback
adds stable confirmed failures to the same regression suite.

[E21](../../evaluations.md#e21-direct-skill-and-lifecycle-qualification) records the scoped
diagnostics and matched clause comparisons, with raw and semantic verdicts separate.
The separate native CLI hook observations are recorded there with their source and limits.
Native skill discovery remains `UNVERIFIED`. The later browser observations in E21 qualify the
named interactions on the saved artifacts; they do not establish human learning, parity with
inspirations or general reliability.

## Research basis

The composable lifecycle (1.6.0) rests on sources read on 2026-10-09. AWS's AI-Driven Development
Lifecycle composes a route for each piece of work from shipped scopes and plans again only the
stages not yet reached; BMAD, Spec Kit and OpenSpec layer a project's overrides over shipped
files. OMG Essence keeps a kernel and composes practices on it; the Disciplined Agile toolkit offers
several lifecycles with a way to move between them; the Kanban Method starts from what a team does
now; Shape Up fixes a time bound and varies the scope. Independent accounts found fixed spec-driven
sequences oversized for small tasks. No source compares an adaptive lifecycle with a fixed one, so
this design's benefit is a claim its validation tests, not a finding. From the research library:
`practices/work-breakdown.md` P5 and F12 (an acceptance boundary only at an irreversible edge, an
outside contract or an unsettled intent), `practices/agent-workspace.md` W0 (the cost of text every
task loads) and `practices/skills.md` (constraints written only as skill text are the least
followed).


Read through `outcomebound research` on 2026-10-07, from the clone working tree at
`da3a7f815fe0`: `practices/agent-evals.md`, text sha256 prefix `a58caafe863c`.
It supports outcome grading, positive and negative controls, isolated trials, and separation of
regression from capability questions. This design applies that method to OutcomeBound; it does
not treat the research as a grant or as proof of this release.

The primary [agent evaluation guide](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
was read on 2026-10-07. It supports that method; no result from that guide is an OutcomeBound
measurement.

Additional research read at the same clone commit: `practices/skills.md` (text sha256
`f75cd0b9573c`), `practices/testing.md` (`0e6b17f62e76`), `practices/review.md`
(`82cb9f7e7868`), and `practices/git.md` (`239f573590a7`). These support the
conditional test, review and adoption candidates in the skills and install designs. The
recorded traps and public guidance justify checking the candidates; their local behavioral
benefit remains UNVERIFIED.
