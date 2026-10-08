---
name: lifecycle
status: draft
---

# Lifecycle support — design

This draft targets v1.5.0. It records the cross-area decisions needed to build the release.
Before it lands, the ticket breakdown and required independent review must settle its scope.
The requirements below are proposed product contracts, not claims that the release has passed.

## Outcome

An adopting project can carry an idea through the applicable stages to a high quality result,
keep its requirements and authority intact at each handoff, and see the evidence for delivery,
operation and eventual retirement. The route fits the project's users, risk and lifespan.
OutcomeBound supplies skills, bounds, guidance, tools and quality controls where they change a
decision or catch a material failure. It does not impose every stage on every change.

## Requirements

R1. Support the full applicable lifecycle: idea and discovery, requirements, design, accepted work, implementation, validation, review and landing, release, deployment, operation, incident and feedback, maintenance and retirement.
R2. [assumed] At each applicable transition, identify the input, output, owner of the next action, authority, completion evidence and when the transition can be skipped.
R3. [assumed] Preserve source requirements through design and tickets; distinguish source accounting, requirement mapping and evidence that the result meets the requirement.
R4. [assumed] Make evaluation evidence reliable before it is used to justify instruction changes; correct the confirmed defects in [issue #95](https://github.com/rajasdevel/outcomebound/issues/95).
R5. [assumed] Identify direct behavior coverage for every shipped skill; add or rerun missing and affected cases, reuse valid unchanged evidence, and check useful behavior retained from inspirations.
R6. [assumed] Preserve project-owned work through adoption and make native skill persistence, loading and hook execution separate observable claims.
R7. Target v1.5.0 for all known in-scope defects and justified improvements; resolve valid failures before release rather than rename them as missing evidence.
R8. [assumed] Keep supported install and command contracts compatible, preserve project gates, and qualify the exact release tree before publication and downstream adoption.
R9. [assumed] Include security, privacy, accessibility, reliability, performance, compatibility and recovery where the project's outcome or changed risk requires them.
R10. [assumed] When this work establishes a new general lesson, return it to research through the existing contribution route. Otherwise retain the existing research. Keep product evaluation results in this repository.
R11. Keep hook installation and execution portable with no unnecessary external tooling; distinguish the engine runtime from a project's genuine check dependencies and make missing setup explicit without weakening checks.

The release goal supplies R1, R7 and R11. R2–R6 and R8–R10 are the design's interpretation of complete
lifecycle support and the existing contract. They are reviewable assumptions, not new grants.

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| v1.5.0 is the target for the complete known scope; a validated defect or justified improvement found while carrying it out joins that scope | scheduling known work across further releases merely to make this release smaller | user | decided |
| Full support means a usable, checked route across every applicable transition; stage names do not by themselves justify skills, tools, records or approvals | a mandatory sequence or a separate skill for every stage | agent | assumed |
| The lifecycle route belongs in an on-demand reference of `using-outcomebound`, installed with that skill; the human guide links to it. The core entrypoint routes there only when a task needs coordination across stages or delivery has stopped before its outcome | a repository-only guide that installed agents cannot find; expanding the always-loaded kernel | agent | assumed |
| Existing area designs keep ownership of their contracts. This design owns transition coverage and release evidence, not copies of wire formats or engine behavior | a second master specification that repeats each area's decisions | agent | decided |
| Risk dimensions are selected from the outcome and changed surface. A small local change needs no service owner or operational exercise; a service change cannot omit applicable security, privacy, accessibility, capacity or recovery questions merely because unit tests pass | a universal audit checklist; a claim that the quality floor proves product quality | agent | assumed |
| Requirements-to-ticket mapping stays optional in the general engine. This release's source-driven breakdown uses `satisfies` and a semantic review; an id proves accounting only | a new refusal or a requirement-id list treated as proof of implementation | agent | decided |
| Known grader defects are repaired before candidate behavior is judged. An unreadable or denied effect remains UNVERIFIED; an observed wrong effect is FAIL | counting an attempted command as an effect; hiding a behavior failure by broadening a grader | agent | decided |
| Qualification uses a deterministic floor, direct skill and transition scenarios, independent cases, and real adoption. It makes bounded claims, not a promise about every future task or every model | universal proof; shipping known valid in-scope failures and waiting for field reports | agent | assumed |
| A new skill must have a distinct trigger and an unserved repeatable decision. A case first runs against current guidance; a missing reference, tool check or narrow clause is preferred when it resolves the failure | an operations, retirement, security or architecture skill selected from its stage name alone | agent | decided |
| A native harness claim needs a native observation with the installed bytes and environment identified. Tests of the engine or an isolated evaluation runner do not establish hook events or skill discovery | inferring native execution from a configuration file or a successful direct invocation | agent | decided |
| Research provides dated evidence and alternatives. Product-specific changes and results stay here; a new general finding is prepared for the existing research contribution path | editing the shared research clone or publishing an anecdote as a general rule | agent | decided |

## Transition coverage

| Transition | Existing owner | v1.5.0 completion evidence |
| --- | --- | --- |
| Idea to framed outcome | `gather-requirements`, `using-outcomebound`, decision support | A bounded ambiguous request becomes a clear outcome, assumptions and reserved decisions, without unnecessary questions or ceremony. |
| Sources to requirements | sources design, `gather-requirements` | Requirements retain their constraints, provenance and correction history; visual requirements retain unshown states and unresolved comparisons. |
| Requirements to design | contract's spec mechanism, `explain-spec` | The design settles downstream choices and material quality dimensions; explanation names gaps without claiming a person's understanding. |
| Design to accepted work | tickets design, `slice-tickets` | The breakdown covers the accepted outcome without inflating ticket count; source mappings and semantic review agree. |
| Accepted work to implementation | `hand-off-tickets`, multi-agent and workspace guidance | A direct handoff preserves scope and authority, provides only the required package, and uses current artifacts. |
| Implementation to validation | `tests-worth-keeping`, floor, validation and runtime guidance | Tests catch the named risk; runtime evidence covers the changed path; missing tools and pre-existing failures are reported accurately. |
| Review to landing | `review-findings`, review design, project gate | Findings have checked dispositions and the exact landing uses the project's gate. |
| Landing to release and deploy | distribution design, CI release and deploy guidance | Built, published, deployed and observed identities remain distinct; indirect effects and recovery stay inside authority. |
| Delivery to operation | deploy, runtime and commands guidance | A finite observation requirement, operator, response route, recovery limits and unavailable telemetry are handled without starting an ungranted ongoing job. |
| Incident and feedback to maintenance | `diagnose`, requirements and research guidance | Evidence separates cause, symptom, correction and recurrence; a defect or changed outcome returns to the appropriate stage. |
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

Use the current tools and evidence records. This work adds no new qualification framework,
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

One qualification table in the existing evaluation record links the cases, candidate identity,
verdicts and limitations to the runner's files and native observations. Review the actual
outcomes before closing the work. A model-call or summary exit code is not a behavior verdict.
These obligations remain required even though no new aggregate gate is built.

All known valid in-scope failures must be fixed and checked before release. Missing required
evidence cannot pass through documentation or a waiver. General skill superiority, every model
and every platform are not claims this bounded qualification establishes. Post-release feedback
adds stable confirmed failures to the same regression suite.

[E21](../../evaluations.md#e21-direct-skill-and-lifecycle-qualification) records the scoped
diagnostics and matched clause comparisons, with raw and semantic verdicts separate.
The separate native CLI hook observations are recorded there with their source and limits.
Native skill discovery and browser interactions remain `UNVERIFIED`. These results do not establish
parity with inspirations or general reliability.

## Research basis

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
