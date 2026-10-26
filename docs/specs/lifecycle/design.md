---
name: lifecycle
status: ratified
---

# Lifecycle support — design

This design recorded the cross-area decisions for v1.5.0, which shipped on 2026-10-08, the
composable lifecycle of v1.6.0 (R12 to R17 and the section of that name) and, from 1.8.0, the
report of the work in flight, `outcomebound where` (the section "Where the work stands"). It is the current design
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
R11. (The hook it names is retired in 1.7.0.) Keep hook installation and execution portable with no unnecessary external tooling; distinguish the engine runtime from a project's genuine check dependencies and make missing setup explicit without weakening checks.
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
| A transition is a change of exposure or of route. Its inventory holds the fragment diff, the work in flight read from the ticket export, the worktrees, the open briefs, the standing grants and any partial deploy, what each item now owes, and what the change invalidates; until the route is decided, the inventory and the brief are the only writes, and each record of the work in flight stays as it is (between the scaffold's lifecycles, the agent runs the scaffold's plan with `--from`, which writes nothing, for the parts the move adds); once decided, the stages not yet reached are planned again, and so is each finished stage whose evidence the change invalidates (it keeps its dated result as history and reads `UNVERIFIED` for the new exposure). Where the person has not decided, the inventory goes to them as one decision brief. A person's directive that names the new route completely is the decision, and adds no ceremony: the agent writes the dated `Changed —` line with the person's words, runs the transition inventory, applies what the directive settles, and draws a brief only for what the directive leaves open, so a directive that leaves nothing open gets no brief (maintainer, 2026-10-14, made exact by the maintainer, 2026-10-15). A directive is complete where it names both the route (a lifecycle template, or the fragment set) and the exposure. A directive that names only an exposure fact (a first outside user, a second maintainer, a client contract) is partial: the inventory runs, the brief asks for the route, and the `Changed —` line is written when the brief is answered. The `lifecycle-switch` fixture's prompt ("I have just invited the first outside user") names an exposure fact and no route, so it is the partial case, and the fixture, which requires the change held for the person and nothing switched by itself, stays as it is, as do E25's recorded results for it. The line and the commit that adds it are the record. Only the latest `Changed —` line of each stream stays in the `local` fragment: an older one leaves the fragment in the change that writes the newer one, and Git history keeps it, so the text every session loads stays bounded (maintainer, 2026-10-15). Where adoption refuses the change, the `Changed —` line reads approved, not applied. This text is shipped. After a complete directive (route and exposure) the agent applies it with its line and its inventory and draws no brief; a partial one gets the brief that asks for the route; the older line of the stream is removed. The rule is in the section of `skills/using-outcomebound/references/lifecycle.md` on a change of exposure or route, in the `"Changed —"` bullet of `skills/adopt-outcomebound/SKILL.md`, in `templates/fragment-local.md`, and in the `"Changed —"` notes of the templates in `templates/lifecycle/`. The templates' example line shows the quoted form, one line for each stream: `Changed — <date> (stream: <stream>): "<the person's words>", decided by <who>; retired "<old term>"; invalidated <what no longer holds>.` The example holds placeholders only, so that the quoted words are the record and a retired term quoted there does not count for `retired-reference` | automatic switching; restarting the work in flight under the new route; a second yes for a route the person already named; a brief that only records a decision the directive already made, which costs the person a read and changes no decision; every `Changed —` line kept in the fragment, which every session loads and which grows with each transition | user | decided |
| The comparison templates are four presets of facts, `prototype`, `solo`, `team` and `organization`, and six overlays, `client`, `eu-market`, `safety-critical`, `audit`, `unattended-agents` and `ai-product`, renamed from `personal`, `shared` and `client` (maintainer, 2026-10-15; the [scaffold design](../scaffold/design.md) lists the files). Each holds example `local` lines, a fragment list, a fits-when line, leave-when rows that include the moves back, and the name of its scaffold set | three templates on one axis, which give a one-maintainer project with many users, a small team selling in the EU and a project with unattended agents no fit; a template per kind of company | user | decided |
| `land-change`, `run-acceptance` and `sync-tracker` ship in 1.6.0, before a case has run against the text they replace; the ten-skill default install becomes thirteen (maintainer, 2026-10-10) | stage support as text only, with skills after fixtures show that the text does not resolve the case | user | decided |
| `adopt --check` and `--detect` print one line for each signal a file shows that the recorded exposure or fragment selection contradicts, refuse nothing and change no exit code | no check until a fixture shows that the exposure lines change an agent's choice; a form check of the record | agent | decided |
| A standing grant for a tracker write covers it when it names the kind of write, the notifications and automations that write is known to start, and the conflict rule; any other write goes as a decision brief. Comment-only is not a universal rule, since what a write starts depends on the tracker and its automations (maintainer, 2026-10-14) | a grant limited to comments; a grant that names the tracker alone | user | decided |
| A production read is allowed with a read-only credential the project gave, under a grant that names the target and its end, and a costly read on a loaded system is named in the grant; a credential that bypasses a control stays forbidden. The `runtime` and `deploy` fragments say the same (maintainer, 2026-10-14) | a ban on every production credential; a read under any credential the agent can find | user | decided |
| A retired term, path or command gets an entry in the project's `.outcomebound/retired.json` in the change that retires it, so a copy left in a guide or a playbook fails `instructions check` (the [instructions design](../instructions/design.md) owns the file and the check). The lifecycle reference tells the agent where: the transition inventory's "what to retire" item lists the entries the change adds, and once the change is decided the agent writes them in the commit that adds the dated `Changed —` line, quoting the old term in that line so the line itself does not count; and the "Maintenance to retirement" row adds an entry for each path, command or process step it removes once the removal is authorized. A process cut outside a transition (a step dropped from the project's own route document) adds its entry in the same change, which the same reference says. Where a floor is installed and holds no `docs.retired` claim, the change that adds the first entry adds that claim too (the [floor design](../floor/design.md)), so the check runs at each `floor check` from then on, not only when someone runs `instructions check` by hand | a kernel line for each retirement, which every task would load; a list the engine fills from a diff, which cannot tell a renamed step from a retired one; leaving the copies to review, which misses copies in adopting projects | agent | decided |
| A recurring job that outlives the task, and a probe a sandbox denied, get no new kernel sentence: the lifecycle reference already requires a grant that covers a new ongoing job's scope, owner and stop condition, and the `commands` fragment already reads a denied probe as `UNVERIFIED` and a job that outlives the task as needing a grant. The field shows one instance each | a kernel line for each | agent | decided |
| `outcomebound where` reports the work in flight from what the project already keeps, each line with its source and a verdict, and names the skill that serves an unfinished item from a table in the engine, keyed by the kind of open item. It writes nothing, starts no process but `git` and `gh`, and is run by an agent or a person, never by a hook. Approved for 1.8.0. The section "Where the work stands" holds the inputs, the output and the limits | a lifecycle file with stage tables (the row on the `local` fragment); a text-only "Next:" clause in each skill, which every task would load and which repeats the lifecycle reference; a hook that prints the state at each turn start, since a hook costs time at every turn end and the engine installs none | user | decided |
| A lifecycle verb ships for a failure that real session records show, and not for a gap that only the text of a skill shows (the same bar that the skills design sets for a skill). Two verbs are not built in 1.8.0. `tickets handover` would print one handover block for a ticket. `acceptance check` would check the form of one acceptance record. Each waits for a case in which a later step failed because the record lacked a field, or in which an outside person accepted a build. `tickets verify` and `outcomebound where` are built because the records showed the failures they serve: claim runners written by hand, closings that named checks the claims plan did not hold, and state read again after a compaction. The records are private, so the reading of them is `UNVERIFIED` here | building all four verbs from a rating of each transition in the text of the skills; building none | user | decided |
| These are not shipped in 1.8.0: a report of the time and tokens of agent sessions, a count of working-file changes in `size`, a check of open rows and unsourced requirements in a spec, and a roll-out of a release across many projects. The first reads the session formats of each harness, which change often, and it serves mainly to measure the engine itself. The second counts file changes that nothing waits on. The third is served by the open rows that a decision brief already carries. The fourth writes into many projects, and no bound for such a write is defined. This repository may keep such a tool for its own use. The reasons are not measured | shipping them now; the session report and the vendored engine are also rejected in the skills design and the install design | agent | assumed |
| The install mode is part of the route (1.10.0; the [install design](../install/design.md) holds the overlay). The lifecycle reference names, as a default the person changes, the stages where a worktree runs facts-only: the build of an accepted ticket whose brief settled its outcome and checks, and a fix with a reproduction in hand, since the facts and the skills carry what such work would fumble without and the general guidance adds input and no measured outcome; and the stages that keep the full install: intake and definition, design, slicing, review and landing, acceptance, release, a transition of exposure or route, and any work whose outcome or bar is unclear. The person sets the mode when the worktree for a ticket is made (`adopt <worktree> --facts-only --local`) and the handoff names it, so that a session that resumes knows which text it runs under; `adopt --check` and `workspace audit` report it. Nothing switches by itself, and the mode is never read from the stage: a ticket's build that turns up a design question goes back to the full install by the person's word, which the reference says | a mode chosen by the engine from the ticket's shape; the full install everywhere, which pays for guidance on routine work, or facts-only everywhere, which drops the guidance where the measured gaps are; a project-wide switch, which the install design's committed mode already is | agent | assumed |

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
decision brief. Once decided, it adds a dated "Changed —" line to Context, removing the stream's
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
a fenced block (closed, as CommonMark reads it, only by a fence of the same character and at least
its length, so a shorter fence inside a longer example does not end it) and with a reason; the line changes class and prints beside the current evidence, as
`…; settled by the person: <reason>`, so a settlement that no longer fits is seen, and no ledger
keeps it. A declared edge silences a line only where it starts with the act, after an article,
and names the act's object where its verb has other uses (a publish, a tag, a push, upload or cut
of a tag, package, release or registry, a release of a version, package or build; a deploy or
redeploy, a promotion, going live, a push, release, ship or roll to production), never by the
words `production`, `tag`, `deployment`, `promotion`, `release` or `registry` alone, so an edge for
another act (deleting a deployment cache, releasing a database lock) leaves the line.

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

## Where the work stands

`outcomebound where [TARGET] [--tickets FILE] [--plan FILE]... [--cwd DIR] [--base REF] [--offline]
[--json]` answers what a person asks after a pause or a compaction: what is in flight here, and
what serves the next step of each unfinished item. The target is a folder in a Git work tree
(default `.`). The code is `outcomebound_tools/where.py`; the `--json` format is
`schemas/where.schema.json`. A run reads `.agents/work` to a depth of four folders and enters no
folder below it, so it takes seconds, not milliseconds, on a large folder. It writes no file in the
project; the interpreter's own bytecode cache of the engine is not the project.

**It reads only what the project already keeps.** Each input is read with the engine's own reader,
so the report agrees with the verb that owns the file:

| Kind | Read from | Reader |
| --- | --- | --- |
| `git` | the current branch, its upstream, ahead and behind counts, the uncommitted paths | `git`, read-only: optional locks off, no lazy fetch from a partial clone, and the plumbing that does not refresh the index (as `size` does) |
| `worktree` | each other worktree: its branch, whether its commits are merged, pushed or only local, and its uncommitted paths; a count of worktrees with no readable install, one older than the engine, or one missing on disk or not committed; a line on this checkout's own install where it is missing on disk or not committed (the [install design](../install/design.md), Install survival) | `git worktree list`, `workspace.default_branch`, `workspace.classify` and `workspace.changes` (the readers of `workspace audit`), `adopt_worktrees` |
| `pr` | the open pull requests of the repository | `gh pr list`, only when `gh` is found on `PATH`'s absolute entries and answers; `--offline` skips it |
| `ticket` | the open tickets of the declared store, from its export (`--tickets`, else `issues.json` at the work tree's root, else at the main checkout's): hold, blockers, `waits-on` | `tickets_store.read_store` |
| `validation` | each claim of a validation plan (`--plan`, repeatable, else the `claims` plan the ticket declaration names; `--cwd` as `validation status` takes it): the last kept result and whether a declared path changed since | `validation.claim_states`, which `validation status` prints and `where` reads |
| `review` | review files in `.agents/work` of this folder and of the main checkout: findings without a disposition; a review of this branch's commits and the paths that differ now | `review_check.sweep`, which keeps the ref each file says it read, and `size.tracked_changes` with the untracked paths, which is the comparison `review since` makes, without its hunks |
| `brief` | briefs an open ticket waits on, and briefs defined in the newest handoff, with the `Decided:` lines recorded for them | `brief_lookup.scan` and `brief_open.split`, the readers of `brief open` |
| `handoff` | the newest file in `.agents/handoffs` (this folder and the main checkout): its age, and the commits on `HEAD` since it was written | the file's time, `git rev-list` |

**It prints one line for each item**, never a sequence: `<VERDICT> <kind> <subject>: <text>
[<source>]`, then `; next: <skill>` where the item is unfinished. The lines come in the order of
the table, which is a fixed order of reading and says nothing about the order of work. The
verdicts:

- `OPEN`: the item owes something. A pull request is open; a ticket is ready to hand off; a brief is
  unanswered; a review file fails `review check` (a finding without a disposition is the common
  case); the last kept result of a claim is `FAIL`.
- `STALE`: a result that was read stands behind the tree: a declared path of a claim changed since
  its result (`CHANGED` in `validation status`).
- `CLEAR`: the source was read and owes nothing: no open pull request; every claim is `CURRENT` with
  a last result of `PASS`; a review of this branch that no file now differs from; a brief that an
  open ticket waits on and that has a `Decided:` line.
- `NOTE`: a fact with no judgement: the branch, a worktree, a ticket that waits or is held, a count
  of what is not listed, a review whose files differ now, the newest handoff.
- `UNVERIFIED`: the source could not be read, and the line says why and what would read it: `gh`
  absent, offline or not signed in; no ticket export; no validation plan; a claim whose last result
  did not run to an exit, or whose result `validation status` reads `UNVERIFIED`; no base to tell
  which reviews concern this branch; a brief id that no file defines, or that two different questions share; a worktree whose folder is gone; a
  ticket claim, which the pinned export does not carry.

**The next skill** comes from this table in `where.py`, keyed by the kind of open item, and nothing
else:

| Open item | Skill |
| --- | --- |
| an unanswered brief | `decision-brief` |
| a claim whose last result failed | `diagnose` |
| a claim whose declared paths changed since its result | `tests-worth-keeping` |
| a review with a finding without a disposition | `review-findings` |
| an open pull request | `land-change` |
| a ticket ready to hand off | `hand-off-tickets` |

A claim whose last result failed takes the first row even when its paths also changed. A test
holds that every name in the table is a shipped skill and that the schema lists the same names. An
item with no row (a worktree, a held ticket, a review whose files differ, an unreadable source) has
no `next`. The `tests-worth-keeping` row names the skill that judges what a check shows; the
rerun itself is the claim's command, which the line's text carries.

**How an item is chosen, where a source holds more than the work in flight.** A project's folders
keep every brief and review it ever wrote, so the verb names the ones that something in flight points
to, and counts the rest on one `NOTE` line, so that a false `OPEN` never buries a true one:

- a worktree is listed when its commits are only local or unknown (held by no remote-tracking
  branch and not by the default branch), when it holds uncommitted paths, or when its folder is
  gone; the others are named on one line. This is the classification of `workspace audit`. After a
  squash merge a landed branch reads `pushed` or `local`, since Git cannot tell it from an unlanded
  one. A count of worktrees with no readable install, one older than the engine, or one missing on
  disk or not committed follows, from the logic of `adopt --check`, and a `git` line names this
  checkout's own install where it is missing on disk or not committed;
- every open pull request of the repository is listed, the one whose branch is the current branch
  first and marked; `gh` is asked for up to 1000, and a list that long reads `UNVERIFIED`. `gh` runs
  with prompts and its update check off;
- a brief is listed when an open ticket names it in `waits-on` or the newest handoff defines it; the
  other briefs with no `Decided:` line are counted, and the line says that an answer recorded before
  the `Decided:` form shows as unanswered. A brief id that two different questions share (a
  collision in `brief open`) reads `UNVERIFIED`, since a `Decided:` line cannot be told to answer
  this one; a line a brief carries to say what waits on it is printed with it; an answer given in a
  ticket comment is not read, and the ticket line says so. The newest handoff is the newest of the
  folder, and may belong to another task;
- a review file is listed when it has a finding without a disposition, or when its `Reviewed:` ref
  names a fixed commit that `HEAD` holds and the base does not. A ref is fixed when it is an object
  id or a tag; a branch, `HEAD`, an expression built on them (`HEAD~0`) and free text are counted,
  never tied. The base is `--base`, else the merge base of `HEAD` with `origin/HEAD` (a pushed copy
  of the branch does not move it), else the base `size` chooses; where there is none, the line is
  `UNVERIFIED` and only open findings are listed. A tied review is `CLEAR` where no file now differs
  from the commit it read and a `NOTE` naming the files where some does, since the files change
  when the findings are fixed and whether to review again is the project's call;
- a ticket is `OPEN` with `next: hand-off-tickets` when it is open, has no hold (`yes` and
  `requested` both hold), has no blocker that the export does not show as a closed ticket, and
  waits on no brief that is unanswered; a blocker that is not a ticket counts as open. A ticket for
  which the export reports a partial answer (`EXPORT_PARTIAL`, `EXPORT_TRUNCATED`) is `UNVERIFIED`
  and is not judged, and an export that is not the whole issue list says so on its head line. A ticket
  that waits on an unanswered brief is a `NOTE` and the brief carries the `OPEN` and
  `decision-brief`, so one thing is not reported twice. Whether a ticket is claimed is
  `UNVERIFIED`: the pinned export carries labels and blockers, not assignees or comments. The
  export's age is printed, since the report is only as current as the export;
- for a validation plan the text prints one line of counts and one line for each claim that failed,
  changed, or whose result is not a `PASS` that `validation status` reads `CURRENT`, each with the
  claim's command; a claim that has no result kept is counted only. The plan is `CLEAR` only when
  every claim is `CURRENT` with a recorded `PASS`.

**The `--json` report** holds `items` (the lines above, with `kind`, `source`, `subject`, `verdict`,
`text` and `next`; `source` and `text` are not empty and `next` is on an `OPEN` or `STALE` line, which the
schema's keyword subset cannot say and the tests hold), `counts`, `read` (the base used, the export's source and age, and the roots
searched) and `does_not_establish`. It has no time of its own: an age is a count of seconds.

**Exits.** 0 once a report is printed, whatever its verdicts, since it is a report and not a gate; 2
for a usage error. A folder outside a Git work tree, or a machine with no `git`, gives `UNVERIFIED` for the Git items
and still reads the files. The verb has no limit on the number of lines and no threshold.

**What it does not establish.** That a line is current beyond the moment it was read (an export, a
result and a handoff are each as old as the line says); that a pull request has passed CI or been
reviewed; that a ticket has no branch or worktree under way (no line joins a ticket to a branch); that
a brief with no `Decided:` line is open outside the briefs it names; that a review of other
commits, or of a moving ref, holds no finding; that a handoff belongs to this task, or that the
commits counted since it (by commit date, which a rebase moves) are new; what the person intends
next; how long anything will take. A handoff is a claim, so its line points at the sources above it
and grants nothing.

**Why it is not a stage table.** The row of the Decisions table that refuses a lifecycle file
with stage tables refused a copy of routes the project writes down, checked only against a model's
own text. `where` differs on each count that row rests on. It reads no file that lists stages and
writes none. Its keys are kinds of open item found in files (an unanswered brief, a failed claim),
not stages of a route: such an item needs the same skill under any route a project has, a
prototype's or a client's. No verdict comes from the position of a line: a ticket line reads the
brief's answer, never where the brief stands in a sequence. Removing the table leaves a complete
report without the `next` field. It names no order, owner or gate. The table is the engine's and
ships with it; it holds six rows, each a skill the engine already ships.

The `workspace` fragment names `outcomebound where` once, for resuming work and after a compaction. The transition inventory of the lifecycle reference reads the same inputs by hand, and does not point to the verb. A person also finds the verb through `README.md` and `outcomebound --help`.

**Validation.** `tests/test_where.py`, with temporary Git repositories and a stand-in `gh`: each
kind with a source that reads, one that does not (`UNVERIFIED` with its reason), and one that is
empty; an export cut short, a result with no verdict, a pushed branch, a missing `git`; each row of the next-skill table; the choice rules above (an answered brief, a brief id that
no file defines or that two different questions share, an old review of other commits, a review of a moving ref, a held ticket, a worktree
read from its main checkout); that no file or index changes in a run; that no process other than
`git` and `gh` starts; that `--offline` starts no `gh`; the shape of the `--json` report against the
schema; and that every skill the table names is shipped. The verb is in the launcher help tests.

## Area updates

| Work | Authoritative design or record |
| --- | --- |
| Evaluation outcomes, fixture contracts, skill coverage and behavior evidence | [skills](../skills/design.md), `evals/README.md`, `docs/evaluations.md` |
| Provenance and semantic coverage limits | [sources](../sources/design.md), [tickets](../tickets/design.md) |
| Portable adoption and native surfaces | [install](../install/design.md) |
| Native prompt, Stop and retry observations (1.5.0 and 1.6.0; the hook is retired) | [E21](../../evaluations.md#separate-native-hook-observations), [finish-check](../finish-check/design.md) |
| Release identity, packaging and publication | [distribution](../distribution/design.md), `docs/VERSIONING.md` |
| General lessons and product-specific evaluation records | [research](../research/design.md) |
| The report of the work in flight, `outcomebound where` (`outcomebound_tools/where.py`, `schemas/where.schema.json`) | this design, the section "Where the work stands"; the readers it uses stay with [workspace](../workspace/design.md), [size](../size/design.md), [floor](../floor/design.md) and [decision-support](../decision-support/design.md) |

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
6. Retired with the finish check in 1.7.0: OutcomeBound installs no hook, so no hook row is
   observed.
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
