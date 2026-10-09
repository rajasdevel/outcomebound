---
name: skills
status: ratified
---

# Skills — design

## Outcome

An adopting project's agent loads a skill exactly when the task calls for it, and the skill
changes what the agent does in the way the project wants: it serves a pain adopters have, says
nothing the co-loaded text already says, and is true of the engine it names. This design decides
which skills OutcomeBound ships, what a skill must earn to ship and to stay, and how one reaches a
project. The rules for the text are `docs/prompt-standard.md`'s; how a skill is written into a
project is the [install design](../install/design.md)'s. The pains and the comparison with public
skill sets are in the [skills
research](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/skills.md).

## The set

| Skill | The pain it serves | Installed |
| --- | --- | --- |
| `using-outcomebound` | process that outweighs the change; "done" that is not evidence | every install |
| `decision-brief` | too many questions, asked badly; authority the harness cannot read | every install |
| `gather-requirements` | an unclear outcome: guessing, or asking too much too late | every install |
| `tests-worth-keeping` | tests that cannot fail for the reason they name; a project that starts red | every install |
| `diagnose` | a fix made for a cause nobody found: the symptom patched, the report never reproduced, a second try that varies the first | every install |
| `review-findings` | a review finding acted on as an instruction, and a disposition nobody recorded; the claim a reviewer got wrong is built anyway | every install |
| `explain-spec` | a person who must act on a spec they did not write and does not follow it; a spec whose gaps only a reader's questions show. It explains and asks, and never claims the person understands | every install |
| `slice-tickets` | work cut to the wrong size | every install |
| `hand-off-tickets` | one ticket shape for every implementer: detail that narrows a capable model, too little for a small one. It says what an implementer is given, never how it works the ticket | every install |
| `explorable` | a decision, lesson or interview that text serves badly: values a person may judge differently, a mechanism they must learn by trying it, or many questions that are easier to answer on a page | every install |
| `adopt-outcomebound` | installing OutcomeBound | never: an agent asked to adopt reads it from the engine checkout |

## Decisions

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| A skill ships only for a pain adopters have, observed in this repository's research or an adopter's history, that the kernel and the text loaded beside it leave unserved (maintainer, 2026-10-06: a requirements-import capability and a teaching step are also wanted; import is the `outcomebound sources` verbs and a paragraph in `gather-requirements`, not a skill of its own, and teaching is `explain-spec`) | a skill per mechanism or per habit, such as a test-first skill or a lesson-contributing skill; a skill prescribing the turn of working a ticket, which strong models take unasked and which measured no better than no skill; a skill for choosing an approach, whose pains the core skill, `gather-requirements` and `slice-tickets` serve | user | decided |
| Every skill is in OutcomeBound's own words. An idea taken from a public skill set is credited by a link to its GitHub repository in the README's Acknowledgements, and in detail in the research record; its text is not copied (maintainer, 2026-10-06: the README links the GitHub repositories whose ideas are adopted, and nothing else) | adapting a public skill's text under its license notice; credit in the research record alone | user | decided |
| A skill reaches another only by the name or installed path of a skill OutcomeBound ships; it never sends the agent to a third-party skill | invoking a public skill, whose rules (approval gates, files it writes) come with it, and whose text changes upstream unreviewed | user | decided |
| What the person asks for outranks a skill's default: a request to be interviewed grants the questions, whichever skill runs the interview | a skill that holds to ask-once against the person's request | agent | decided |
| `hand-off-tickets` names a default for an edge that holds only on a condition the implementer may be unable to settle: the smaller change inside `bounds`, reported in its handover (field: a conditional edge left the implementer to guess or stop) | leaving it to the implementer, who then asks or stalls | agent | decided |
| `using-outcomebound` says that a change that is only text for people, or mechanical, meets no row by its size and needs no independent review and no full suite unless a row's condition holds or the project requires them. The existing sentence on a project's suggested process covered a project's suggestion, not the change's size | leaving the sentence as it was; a rule in the kernel, the most expensive text | agent | decided |
| Fragment text for field failures lives in the fragment that the failing work loads, not in the kernel: `workspace` (a shared machine's budget: disk, memory, CPU, cleanup of only what the task made), `multi-agent` (wait once for a running delegate and never poll; one role at a time and the tickets of one landing per worker; a dispatch names the model and effort it chose, since a harness default can be the session's model, and the brief itself carries the bounds, since a delegate may load no project instructions, version 7), `commands` (a probe that fails where the sandbox may have denied it is `UNVERIFIED`; a job still running when the task ends needs the person's grant) | the same text in the kernel, which every task loads | agent | decided |
| Shipped guidance that names a POSIX-only command says so, or gives the portable form, once in the file that holds it (`commands` fragment, `gather-requirements`, the `github` store reference, `docs/tickets.md`); text is not duplicated per command. Whether a PowerShell form runs is `UNVERIFIED` until a Windows run settles it | a PowerShell twin of every command | agent | decided |
| A skill states only what the kernel, the core skill, the decision-brief skill and the fragments a project selects beside it do not | restating the kernel for emphasis | agent | decided |
| Every install carries the ten working skills, `using-outcomebound`, `decision-brief`, `gather-requirements`, `tests-worth-keeping`, `diagnose`, `review-findings`, `explain-spec`, `slice-tickets`, `hand-off-tickets` and `explorable`; no fragment adds or removes one, and `adopt-outcomebound` stays in the engine checkout (maintainer, 2026-10-06) | the four default skills with a fragment's `skills:` adding the ones its setup needs, so that `slice-tickets` and `hand-off-tickets` reach only a project that selects the `tickets` fragment | user | decided |
| `diagnose` and `review-findings` ship as two skills of their own, each with a trigger no existing skill has (a failure whose cause is unknown or a fix that did not hold; a review finding to act on or write), so that one clause in a loaded skill does not load in the wrong situations. The reuse rule (look for what already does it, before writing new code) is one sentence of `using-outcomebound`, since it is part of sizing and has no trigger of its own (maintainer, 2026-10-06) | a skill for reuse; a debugging clause in `tests-worth-keeping`, which says what a test is worth and not how a cause is found | user | decided |
| `review-findings` names a review file format (a `Reviewed:` line, a `### <id> · <title>` heading for each finding, a `Disposition:` line of `fixed`, `rejected` or `deferred` with its where or why) and the verb `outcomebound review check`; `docs/specs/review/design.md` holds the format and the verb, and the skill names the same format | a skill that asks for a disposition and leaves the format to each project | agent | decided |
| Each skill has one eval fixture whose post-checks read the behavior the skill exists for. Until runs of its fixture pass, what a skill does for an adopter is `UNVERIFIED` wherever it is claimed | shipping on reading alone | user | decided |
| `diagnose`, `review-findings`, `explain-spec`, the `runtime` and `deploy` fragments, a reuse sentence for `using-outcomebound` and the visual-inputs paragraph of `gather-requirements` each have a fixture with a case where the text is to help and a case where it must add no work (`diagnose` and `diagnose-typo`, `review-findings` and `review-findings-small`, `reuse-stdlib` and `reuse-none`, `visual-reference` and `visual-none`; `explain-spec` and `explain-spec-none`; the `runtime` fragment, `runtime-check` and `runtime-none`; the `deploy` fragment, `deploy-authorized` and `deploy-wrong-version` with the no-work twin `deploy-none`), and `requirements-replay` has the source paragraph of `gather-requirements` replayed on one issue with a later correction; one run per arm on one model (`docs/evaluations.md` E20): `diagnose` and `review-findings` separated the arms; the reuse sentence did not (both arms passed both of its fixtures), so it is not shipped and waits for a fixture that separates them; the other results are recorded there, and with one run on one model what each does for an adopter stays `UNVERIFIED` | shipping on reading alone | agent | decided |
| Direct cases now load `hand-off-tickets` (`handoff-author-spec` and `handoff-author-outcome`) and `adopt-outcomebound` (`adopt-upgrade` and `adopt-inspect`). [E21](../../evaluations.md#e21-direct-skill-and-lifecycle-qualification) records their scoped results and limits. Prepared-package comparisons and engine tests remain separate evidence; these runs do not establish general skill benefit | treating prepared-package comparisons or engine tests as direct skill evidence | agent | decided |
| A project's required process binds; what its documents only suggest is sized like any mechanism, and the project facts, the contract and the core skill say so; the kernel stays within its 300 words. The ladder's rungs 2 and 3 measure it, in a project whose documents suggest a design note, a record, the full suite and a second reader for every change | leaving a project's suggestions to outrank the sizing the kernel asks for | agent | decided |
| The kernel keeps its sizing paragraph. On the ladder, the install without it matched the full install within one run on every rung, on one model at three runs a cell, which cannot show its effect absent; and it states the rule the rest of the text applies | cutting it on three runs a cell | agent | decided |
| A skill whose fixture shows no difference between the current and kernel-off arms, over repeated runs, is rewritten or cut | keeping a skill because it reads well | agent | decided |
| `explain-spec` installs in every install, as a default skill (maintainer, 2026-10-06). Its trigger is narrow (a person must act on a spec they did not write, or says they do not follow it), so an install that never meets that task loads only its description | installed only where a selected fragment's `skills:` names it, which reaches no adopter whose fragments do not | user | decided |
| Frontmatter holds `name` and `description` only, and the description is the trigger, its key use case in the first 250 characters | harness-specific keys, which one harness reads and another rejects | agent | decided |
| Each skill's description opens with the sentence `Use <condition>.`, where `<condition>` is the pointer line adopt writes for it in `AGENTS.md` (`CONDITIONS` in `outcomebound_tools/adopt.py`); later sentences refine it. `tests/test_skill_frontmatter.py` holds the two equal. A harness shows a skill by both texts, and two hand-written copies had drifted apart on three skills | a pointer derived from the description at install, which makes every pointer as long as the description in text every session loads; two copies kept by review | agent | decided |
| A project that starts from an idea is served by a reference of `using-outcomebound`, `references/new-project.md`, and no new skill: skills reach a project only through `adopt`, so in a folder with no install a new skill is found no sooner than the reference, and the engine's refusal outside a Git work tree and `--detect` on an empty repository name the route instead ([install design](../install/design.md#onboarding)). The reference sizes the idea by who depends on it, frames it with the four inputs, an appetite, no-gos, the strongest case against and a stop rule, probes what could end it with throwaway code, puts what is costly to reverse in one decision table, and builds a walking skeleton whose bar reads `PASS`, `FAIL` or `UNVERIFIED`; each stage says when it adds nothing. An agent's agreement, and users an agent simulates, are hypotheses, never evidence of demand | a `start-project` skill in every install; a stage sequence with approvals between stages, a constitution or a document per stage, which spec-driven tools ship and which practitioners report as review burden on small work | agent | assumed |
| `using-outcomebound` keeps the mechanism table, since its ids are the registry a project's `local` guidance names and the kernel names the mechanisms by description only; it adds a test of required process (a check, hook, CI job or ruleset enforces it, or the text says it is required) against suggested process, sized like any mechanism, and a router to the skill or reference each kind of step needs | dropping the table as a copy of the kernel, which leaves the ids a fragment's Mechanisms line uses defined nowhere a project loads (`tests/test_mechanisms.py` holds this) | agent | assumed |
| `explorable`'s trigger is a page the person asks for or acts on: trying options with their own numbers, or learning a mechanism by trying it. A decision or an interview reaches it through `decision-brief` and `gather-requirements`, which name it where text serves badly | a trigger on every decision whose answer turns on values, which matches nearly every decision brief and loads both skills for one decision | agent | assumed |
| 1.6.0 changes to skill text are of two kinds. Restatement cuts and additions that a review finding, the field or the audit of the set names (a counted intermittent failure, the class of a review finding, evidence per finding, a flaky baseline, the question order of `explain-spec`, what is not a decision brief) ship with their effect `UNVERIFIED` until a fixture shows it. Text whose effect a fixture measured (the baseline sentence of `tests-worth-keeping`, the tier sections of `hand-off-tickets`, the block rules of `slice-tickets`) keeps its place: moving it to another carrier waits for a run of that fixture | moving measured text to references or fragments on a reading of the text alone, which the measured cases might not survive | agent | decided |

## Edges

A new skill, or a change to what one tells a model to do, is reviewed once before it ships (the
`review` mechanism, as for the core skill), since no fixture runs in CI.
Removing a shipped skill removes it from adopters' installs on their next upgrade.

## Validation

`tests/test_skill_frontmatter.py` holds the frontmatter and length; `tests/test_skill_paths_resolve.py`
holds every path a skill names; `outcomebound instructions check` reads the installed copies as
it reads any instruction file; the fixtures are listed in `evals/README.md`.


## Lifecycle support and qualification

The [lifecycle design](../lifecycle/design.md) defines the v1.5.0 outcome and transition
requirements. [E21](../../evaluations.md#e21-direct-skill-and-lifecycle-qualification) records
the scoped qualification, including failures, bounded repairs and evidence limits. Qualification
does not change the decision statuses below.

| Decision | Rejected alternative | Owner | Status |
| --- | --- | --- | --- |
| An on-demand lifecycle reference installs with `using-outcomebound` and routes applicable transitions to existing skills, fragments, project gates and evidence. A human guide links to the same route | a stage checklist added to the kernel; a guide available only in this repository | agent | assumed |
| Every current skill has an identified direct behavior case. Reuse existing evidence only when its instruction, fixture, tool and grader inputs still apply; run the missing or affected cases, including `hand-off-tickets`, `adopt-outcomebound` and `explorable`. Prepared packages, static checks and engine tests remain separate evidence | calling structural agreement or a prepared-package comparison proof of skill execution | agent | decided |
| Graders preserve tool results and supported execution order, associate provenance with the requirement it labels, reject negated or unrelated matches, and disclose all enforced fixture facts. They check outcomes; a lexical result is not a semantic review | making old runs pass by accepting missing labels, denied effects or unauthorized effects | agent | decided |
| Each substantive changed instruction is checked against a named failure or product decision, an independent case and an applicable case where it must add no work. Reuse a control across claims when it exposes each risk. Comparable runs isolate the text being compared where that causal claim is made | a bundle comparison credited to one skill; a rewrite tuned only to a seen answer | agent | assumed |
| `gather-requirements` is checked for source constraints, corrections, stated/inferred provenance and visual gaps. A failing valid case gets a narrow correction; the existing obligations are not diluted | adding another requirements skill or accepting one matched keyword as full source fidelity | agent | decided |
| `tests-worth-keeping` makes explicit that a refusal or deliberate break must reach the behavior it claims to test; a failure at an earlier guard is not that evidence | a blanket mutation-testing step for every change | agent | assumed |
| `review-findings` leaves a finding open during its fix, then completes the available counterexample after the last relevant change before writing fixed or PASS; it compares a substantive rewrite with its prior meaning where that is the review risk | another review round for every edit; sentence counting as proof of preserved meaning | agent | assumed |
| An explicit interview orders questions by settled prerequisites and revisits dependent questions when an answer changes the branch; a learning explorable gives feedback on a prediction and permits a retry where useful. These narrow candidates are checked before being credited as improvements | assuming rounds alone preserve question dependencies, or that a reveal always explains a wrong prediction; imposing either workflow on ordinary tasks | agent | assumed |
| `explain-spec` keeps a decided requirement when code falls short of it and records the implementation gap separately. Clarifying words preserve the decision and its bounds; a decision change uses the authority the project grants | changing the requirement to match the code, or reopening a decided requirement merely because the implementation does not meet it | agent | assumed |
| `decision-brief` delivers the complete rendered brief. A revision changes the input and draws it again, so selected evidence and recovery limits survive delivery | shortening a successful drawing by hand and losing selected content | agent | assumed |
| `hand-off-tickets` delivers the compiled brief with its tier package, either in the message or in an existing file the message names | giving a brief identity and asking a later sender to attach the accepted brief | agent | assumed |
| Existing diagnosis narrowing and source/history due diligence stay unchanged unless a valid case shows a missing behavior; upstream boundary-tracing and prior-refusal recipes are candidates for that case, not automatic new instructions | adding a diagnostic recipe or another decision ledger from text comparison alone | agent | decided |
| A reuse clause is kept only if an existing-project-helper case shows useful behavior against current guidance without adding work to its control | shipping the clause because both arms selected the standard library | agent | decided |
| An adaptation preserves the useful behavior of its cited inspiration within the shared task and authority. Record a pinned source, retained behavior and intentional differences; use a direct comparison where an uncertain difference could affect the result | assuming shorter text is better, or treating a current-versus-none comparison as proof against the inspiration | agent | assumed |
| New operation, retirement or specialist skills require a distinct unserved decision after current guidance is exercised; a narrow reference, fragment or deterministic check can be the complete fix | counting new skills as lifecycle coverage | agent | decided |

The method is a pre-release risk check followed by field feedback. It cannot prove every future
use. Known valid in-scope failures are fixed before release. Claims about comparative benefit state
the tested tasks, candidate and limits; no blanket superiority claim follows from a small pass.
The existing rule on repeated no-difference results stays in force; a saturated fixture or an
underpowered comparison is first checked as a measurement limit.

Use the existing evaluation runner, saved metadata, reports and summary. One qualification table
links the required cases to those records and the review of their outcomes. Do not add an
evidence schema, certificate, aggregate checker or model judge merely to validate that table.
A successful summary command means the summary was produced; its claim verdicts still need
reading. Native hook acceptance needs separate observations; retaining a CLI record alone
does not establish it.

Execution and record details stay in `evals/README.md`; dated runs and method corrections stay
in `docs/evaluations.md`. The runner's bounded native-retention option keeps one matched session
for separate review, not an automatic identity, sequence or behavior verdict. Its current limits
are recorded in [E21](../../evaluations.md#current-bounded-retention-support).
The explain-spec fixture declares its own notes area; the skill gains no universal notes-folder rule.


## Research candidates (not installed)

The [testing guidance trials](../../../evals/research-trials.md) define the comparison before
results are read. Post-patch-validation and useful property selection are candidates for
small additions to `tests-worth-keeping`, not new installed skills. Existing refusal-path
and tautology guidance remains the baseline. A source inspection is not behavioral evidence.

Version-matched tool instructions remain a research-only mechanism until a concrete drift
case shows a gap. The new model and practice records belong in the neutral research library.
They do not by themselves change the kernel, provider defaults, authority rules or model tiers.
The existing instruction review, own-word attribution and evaluation requirements still apply.

The initial trial stopped on instrument defects, as
[E22](../../evaluations.md#e22-testing-guidance-research-trial-and-instrument-correction) records.
The corrected fixtures are kept for a fresh comparison. Neither candidate bullet is installed;
there is no supported paired effect on which to base that instruction change.
