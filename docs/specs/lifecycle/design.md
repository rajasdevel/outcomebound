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
| A new skill must have a distinct trigger and an unserved repeatable decision. A case first runs against current guidance; a missing reference, tool check or narrow clause is preferred when it resolves the failure ; for `land-change`, `run-acceptance` and `sync-tracker`, the maintainer's row of 2026-10-10 below supersedes it | an operations, retirement, security or architecture skill selected from its stage name alone | agent | decided |
| A native harness claim needs a native observation with the installed bytes and environment identified. Tests of the engine or an isolated evaluation runner do not establish hook events or skill discovery | inferring native execution from a configuration file or a successful direct invocation | agent | decided |
| Research provides dated evidence and alternatives. Product-specific changes and results stay here; a new general finding is prepared for the existing research contribution path | editing the shared research clone or publishing an anecdote as a general rule | agent | decided |
| The lifecycle is composable: a core that every lifecycle shares (the kernel, the transition table, the skills); exposure facts for each stream of work; obligations that the exposure facts select; and the project's own routes. A template is a starting comparison, never an install by `adopt`. A new project, or a project on a move the person accepted, can take a preset's files from the scaffold verb, which writes only the files that are absent, records nothing, and leaves them the project's (maintainer, 2026-10-15; the [scaffold design](../scaffold/design.md)) | one static route for every project; a route chosen per repository when one repository holds several streams; templates that never reach a project's files, so each new project's agent picks its own file set | user | decided |
| The exposure facts, each stream's route document, the gate owners, the leave-when signals, the project's measure of a better outcome and the dated changes are lines in the project's `local` fragment, which every task already loads | a separate lifecycle file with stage tables and a form check, which copies routes the project already writes down and checks only a model's own text | agent | decided |
| Obligations are fragments. The adopt skill proposes them from the exposure facts and the signals, and the person confirms; two setup fragments are new: `client` (acceptance by an outside party) and `explore` (work whose aim is to learn) | a closed list of duty ids beside the fragments, which gives one text two selectors | agent | decided |
| A person decides only at an irreversible edge, an outside contract or an unsettled intent; a step inside a unit of work is not a gate | a gate at every stage; a gate named by the stage alone | agent | decided |
| A transition is a change of exposure or of route. Its inventory holds the fragment diff, the work in flight read from the ticket export, the worktrees, the open briefs, the standing grants and any partial deploy, what each item now owes, and what the change invalidates; once decided, the stages not yet reached are planned again, and so is each finished stage whose evidence the change invalidates (it keeps its dated result as history and reads `UNVERIFIED` for the new exposure). Where the person has not decided, the inventory goes to them as one decision brief. A person's directive that names the new route completely is the decision, and adds no ceremony: the agent writes the dated `Changed —` line with the person's words, runs the transition inventory, applies what the directive settles, and draws a brief only for what the directive leaves open, so a directive that leaves nothing open gets no brief (maintainer, 2026-10-14, made exact by the maintainer, 2026-10-15). A directive is complete where it names both the route (a lifecycle template, or the fragment set) and the exposure. A directive that names only an exposure fact (a first outside user, a second maintainer, a client contract) is partial: the inventory runs, the brief asks for the route, and the `Changed —` line is written when the brief is answered. The `lifecycle-switch` fixture's prompt ("I have just invited the first outside user") names an exposure fact and no route, so it is the partial case, and the fixture, which requires the change held for the person and nothing switched by itself, stays as it is, as do E25's recorded results for it. The line and the commit that adds it are the record. Only the latest `Changed —` line of each stream stays in the `local` fragment: an older one leaves the fragment in the change that writes the newer one, and Git history keeps it, so the text every session loads stays bounded (maintainer, 2026-10-15). Where adoption refuses the change, the `Changed —` line reads approved, not applied. The shipped text that must change to match: `skills/using-outcomebound/references/lifecycle.md`, its section on a change of exposure or route, where it says a directive that "names the new route or exposure" is the decision and that the brief "is written even when no fragment changes" (near its lines 97 to 101), and where it adds the line "On a yes" (near its line 118), so that a complete directive (route and exposure) is applied with its line and its inventory and no brief, a partial one gets the brief that asks for the route, and the older line of the stream is removed; the `"Changed —"` bullet of `skills/adopt-outcomebound/SKILL.md`, which says the line is written "only after the person's yes on a transition"; the `"Changed —"` notes of the lifecycle templates, renamed in the same release (the [scaffold design](../scaffold/design.md)): `templates/lifecycle/solo.md` and the new `prototype.md` (from `personal.md`, whose note near its line 45 says "write it only after a person's yes on a transition"), `templates/lifecycle/team.md` and `organization.md` (from `shared.md`, near its line 53) and `templates/lifecycle/overlay-client.md` (from `client.md`, near its line 52; both "written after a person's yes on a transition"), and each new overlay template; and `templates/fragment-local.md` (near its lines 11 to 13, "after a person's yes on a change of route"). Each says instead: after a complete directive or a person's answer to the transition brief, one line for each stream, the older one removed. Design note for the implementer: the templates' example line (near line 30 of `personal.md` and line 36 of `shared.md` and `client.md` before the rename, today `Changed — <date>: <what>, decided by <who>, invalidated <what no longer holds>.`) shows the quoted, one-for-each-stream form, for example `Changed — 2026-10-15 (stream: app): "<the person's words>", decided by <who>; retired "<old term>"; invalidated <what no longer holds>.`, with one such line for each stream and a note that the line replaces the stream's older one, so that the quoted words are the record and a retired term quoted there does not count for `retired-reference` | automatic switching; restarting the work in flight under the new route; a second yes for a route the person already named; a brief that only records a decision the directive already made, which costs the person a read and changes no decision; every `Changed —` line kept in the fragment, which every session loads and which grows with each transition | user | decided |
| The comparison templates are four presets of facts, `prototype`, `solo`, `team` and `organization`, and six overlays, `client`, `eu-market`, `safety-critical`, `audit`, `unattended-agents` and `ai-product`, renamed from `personal`, `shared` and `client` (maintainer, 2026-10-15; the [scaffold design](../scaffold/design.md) lists the files). Each holds example `local` lines, a fragment list, a fits-when line, leave-when rows that include the moves back, and the name of its scaffold set | three templates on one axis, which give a one-maintainer project with many users, a small team selling in the EU and a project with unattended agents no fit; a template per kind of company | user | decided |
| `land-change`, `run-acceptance` and `sync-tracker` ship in 1.6.0, before a case has run against the text they replace; the ten-skill default install becomes thirteen (maintainer, 2026-10-10) | stage support as text only, with skills after fixtures show that the text does not resolve the case | user | decided |
| `adopt --check` and `--detect` print one line for each signal a file shows that the recorded exposure or fragment selection contradicts, refuse nothing and change no exit code | no check until a fixture shows that the exposure lines change an agent's choice; a form check of the record | agent | decided |
| A standing grant for a tracker write covers it when it names the kind of write, the notifications and automations that write is known to start, and the conflict rule; any other write goes as a decision brief. Comment-only is not a universal rule, since what a write starts depends on the tracker and its automations (maintainer, 2026-10-14) | a grant limited to comments; a grant that names the tracker alone | user | decided |
| A production read is allowed with a read-only credential the project gave, under a grant that names the target and its end, and a costly read on a loaded system is named in the grant; a credential that bypasses a control stays forbidden. The `runtime` and `deploy` fragments say the same (maintainer, 2026-10-14) | a ban on every production credential; a read under any credential the agent can find | user | decided |
| A retired term, path or command gets an entry in the project's `.outcomebound/retired.json` in the change that retires it, so a copy left in a guide or a playbook fails `instructions check` (the [instructions design](../instructions/design.md) owns the file and the check). The lifecycle reference tells the agent where: the transition inventory's "what to retire" item lists the entries the change adds, and once the change is decided the agent writes them in the commit that adds the dated `Changed —` line, quoting the old term in that line so the line itself does not count; and the "Maintenance to retirement" row adds an entry for each path, command or process step it removes once the removal is authorized. A process cut outside a transition (a step dropped from the project's own route document) adds its entry in the same change, which the same reference says. Where a floor is installed and holds no `docs.retired` claim, the change that adds the first entry adds that claim too (the [floor design](../floor/design.md)), so the check runs at each `floor check` from then on, not only when someone runs `instructions check` by hand | a kernel line for each retirement, which every task would load; a list the engine fills from a diff, which cannot tell a renamed step from a retired one; leaving the copies to review, which missed 16 in one week, measured in adopting projects | agent | decided |
| A recurring job that outlives the task, and a probe a sandbox denied, get no new kernel sentence: the lifecycle reference already requires a grant that covers a new ongoing job's scope, owner and stop condition, and the `commands` fragment already reads a denied probe as `UNVERIFIED` and a job that outlives the task as needing a grant. The field shows one instance each | a kernel line for each | agent | decided |

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
| one maintainer | `solo`, and a named end for each standing grant (a date, an event, or the owner's revocation) |
| it deploys a service | `deploy` (the gate chain, several changes on one build, an emergency deploy that keeps its production go, the results Successful, Failed and Inconclusive, a closing note where the route or the client asks for one, a copy of production data as the person's decision) and `runtime` |
| it publishes a package | `ci-release`, and consumers moved within a stated window or the hold recorded with an owner |
| it changes stored data | `db-migrations` |
| a client or a regulator accepts the work | `client` (new) |
| its expected life starts with learning | `explore` (new): a stopped probe completes with its learning record and the person's stop decision, and a walking skeleton is kept only where the throwaway boundary names it as kept and the stop decision permits it; a skeleton built as the probe goes with the throwaway parts |

**Routes stay the project's.** Context names each stream's route document and the kind of change
that takes it (`Streams — <stream>: route in <file>; takes <kind of change>`, with an optional
`; fragments <id>, <id>`). A fragment applies to every stream unless a `Streams —` line names it in
that field; then it applies to those streams only. Bounds names each
gate's owner and evidence (`Gates — <gate>: owner <role>, evidence <kind>`). Distinguish holds the
project's own ladder of states. Where a stream has no written route, the adopt skill proposes the
lines for the project's own document, each with the file or commit that shows it. Paths by kind of
change are the kernel's sizing applied to each change.

**Better means.** One Context line holds the project's own measure of a better outcome, in its
words. The misfit report, the stop-or-pivot brief of `explore` and the transition brief judge
against it.

**Leave when.** Bounds lines name each signal that ends the current lifecycle, where it can be
observed (a file pattern, a tracker field, or the person's word) and who watches it, with the
brief it opens: its main value is the inventory of work in flight, and a change of route may turn
no fragment on or off. Moves back are normal rows, and a project may strike a row with its
reason. The agent checks these lines at adoption and at each handoff; the drift lines read the
signals that files show.

**A transition** is a change of exposure or of route: a fact moves, the person gives a directive, a
stream starts or ends, the authority model changes, or a leave-when signal appears. A drift line is
checked against the leave-when rows and the person's words, not a transition of its own. The agent
writes one decision brief with the fragment diff and the work in flight (open tickets from the
export, branches the main line does not hold and their requests, worktrees with uncommitted work,
open briefs, standing grants and their dates, a release artifact not yet published, a deploy or
cutover receipt in a partial phase; what it cannot read is `UNVERIFIED`), what each item now owes, what the change
invalidates, what still holds under a lighter route (data kept, versions supported, consumers,
contract duties) and what to retire. Where the person has not decided, that goes to them as one
decision brief. Once decided, it adds a dated `Changed —` line to Context, removing the stream's
older one (Git keeps it), plans the stages not yet reached and replans each finished stage whose
evidence the change invalidates. A person's directive that names the route completely (the
route and the exposure; one that names only an exposure fact is partial, and its brief asks for
the route) is the decision: the line carries the person's words, the inventory runs, what the directive settles is
applied, and a brief asks only what it leaves open (maintainer, 2026-10-15). Each item in flight keeps the state its own record shows. A resume
that finds uncommitted work and nothing landed since the last handoff is a misfit report at the
handoff, not a transition: it asks whether the pause is deliberate, and the work its grant covers
goes on.

**Templates.** `templates/lifecycle/` holds the four presets and the six overlays the [scaffold
design](../scaffold/design.md) names. A throwaway item needs no template; regulated work takes the
eu-market, safety-critical or audit overlay by the fact that applies. The adopt skill offers the
nearest one as a comparison and names the differences; adoption never installs one. A new project,
or a move the person accepted, takes the preset's files from the scaffold verb.

**Stage support.** `land-change` drives a request and its fix loop to landing; `run-acceptance`
prepares, pre-runs and records acceptance by an outside party; `sync-tracker` reads a tracker that
is not the ticket store into a markdown source (the sources design reads markdown) and writes back
under a grant that names the kind of write, its known notifications and automations and the
conflict rule, any other write being a decision brief. The `gather-requirements`
reference names the source kinds (a transcript, a data trace, a story, a design file). A held
decision brief names its default and its expiry, a moment the person or the project already named,
or says the work waits. The `client` template holds a route example for a client delivery, to
compare with where a project has none.

**Drift.** `adopt --detect` reads two more signals: the authors in the recent history, and version
tags or a `VERSION` file. `adopt --check` and `--detect` compare the signals with the recorded
exposure, the fragment selection and the declared edges, and print `signal present, record says
otherwise` lines. An author is not a maintainer, so the lines claim only what the person recorded
(`solo` selected, an exposure line that says one person), never the absence of `team`. A person
settles a line with `Drift — <signal>: <reason>` on a line of its own in the Bounds slot, outside
a fenced block and with a reason; the line changes class and prints beside the current evidence, as
`…; settled by the person: <reason>`, so a settlement that no longer fits is seen, and no ledger
keeps it. A declared edge silences a line only where it names the act (a publish, a release, a tag
push, a deploy, a promotion, a push to production), never by the words `production` or `tag` alone.

## Transition coverage

| Transition | Existing owner | v1.5.0 completion evidence |
| --- | --- | --- |
| Idea to framed outcome | `gather-requirements`, `using-outcomebound` and, from 1.6.0, its new-project reference, decision support | A bounded ambiguous request becomes a clear outcome, assumptions and reserved decisions, without unnecessary questions or ceremony. E23 ran the new-project fixtures: its table holds the verdicts and their limits. |
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
| A change of lifecycle | from 1.6.0, the lifecycle reference's transitions section, `decision-brief`, the drift lines of `adopt --check` as signals to check, and the scaffold verb's preview with `--from` for the files the new lifecycle lacks | The brief names the fragment diff, the work in flight and what each item owes; nothing switches without the person. E24 ran one fixture pair: no verdict changed at one run a side. |
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
