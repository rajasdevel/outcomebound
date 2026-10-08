---
last_checked: 2026-10-08
volatility: STABLE (dated results of named models and codex versions; the method) / MONITOR (codex isolation and sign-in facts under Method)
sources:
  - https://learn.chatgpt.com/docs/agent-approvals-security
  - https://learn.chatgpt.com/docs/auth
  - https://inspect.aisi.org.uk/model-graded.html
  - https://inspect.aisi.org.uk/handling-errors.html
  - https://arxiv.org/html/2607.27250
---

# Evaluating what model-facing text changes in a coding agent's work

Re-check this record when a pass runs on another model or codex release, when the runner or a
fixture changes, or when a cited study or tool page changes.

**What this answers.** How to measure what a piece of text changes in the work of a coding agent.
The text can be an operating contract, a skill, or a block of project facts. This record also
states what OutcomeBound's own evaluations of its text measured, and the scope of every result.

**Who it is for.** Anyone who checks a claim that OutcomeBound makes. Anyone who writes or cuts
text that a model reads. Anyone who reruns an eval or designs the next one. The
[README](../README.md) states the claims. This record holds the evidence for each one.

How to run the evals is in [`evals/README.md`](../evals/README.md). The general method, with the
published evidence behind it, is in
[`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md)
§9. What published studies say about model judges is in
[llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md).
What they say about statistics, task selection, error analysis and evaluation tools is in
[agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md).

## What the README claims, and where the evidence is

| The README says | Evidence | Scope |
| --- | --- | --- |
| Right-sized work: 6 of 6 against 0 of 6 on the two middle ladder tasks | E10, the ladder rerun | gpt-6.1-sol, 3 runs a cell, one synthetic repository |
| A skipped check is named `UNVERIFIED` with the reason | E1, E10 | E1: the lint that could not run on `small-fix`, gpt-6-sol. E10: the skipped slow suite, in every rung-2 answer with the install, gpt-6.1-sol |
| The install adds about 27% more tokens a run | E6 | gpt-6-sol, the skill fixtures. The ladder rerun's tokens went both ways (E6) |
| No run in any arm interrupted the person | The ladder and its rerun | No ladder or rerun run put a question to the person. Runs in other passes did ask: most runs that stopped short in E14 asked for the merge, and in the wording audit runs ended with a confirmation question |
| The under-engineering side is not separated | E8 | No fixture separates the arms |
| A test-first hand-off took a smaller model from 6 to 9 of 9 | E17, the hand-off comparison, and E18, its rerun | gpt-6-luna at xhigh, three small tasks, 9 runs a cell. The whole gain is one row of one ticket, in both passes |
| Efficiency is an aim, not a measured result | E6, E9, and the token columns of the ladder | Cost per finished task is not measured |
| OpenAI models through Codex; Claude Code controller passes | Model choice, E19, E20, Runs per cell and power | Most Codex comparisons have three runs a cell; hand-off has nine. E19 and E20 have one run per case and arm |
| The floor, the finish check and the instruction check | The engine's test suite | Not measured by these evals |

## The scope of every result

Every result under Results is class O: a run of this repository's own fixtures. In each run, codex
drove one named model in a disposable repository. The effort was medium unless a section names
another effort. Deterministic post-checks graded the runs, except where a section says that a
model judge scored them.

- **Models.** Every candidate model under Results is an OpenAI model that ran through codex,
  except E19 and E20, which ran Claude Sonnet 5.5 through Claude Code subagents, once per
  case and arm. Claude models also
  appear under "Results not kept here": as the judge of one proposal-only sample, and as
  candidates in the slicing arms. Behavior on other model families and other harnesses is not
  measured.
- **Runs.** Most cells hold three runs. The hand-off comparison holds nine a cell, as three
  clusters of three. Three runs show only a large difference. Nine runs also show only a large
  effect.
- **Repositories.** Each fixture family is one small synthetic repository.
- **What a PASS means.** A PASS establishes only what its check reads, for that model on that day.
- **How the counts were taken.** Every count was re-derived on 2026-10-01 from the kept run
  records and result files. The hand-off counts were re-derived again on 2026-10-03. The counts of
  the hand-off rerun were taken on 2026-10-04.

**Evidence classes.** (M) measured. (L) a lab's or vendor's documentation or guidance. (S) a
standard. (P) practitioner consensus. (A) an anecdote or one uncontrolled report. (F) a forecast.
(O) OutcomeBound's own runs and records, with the scope stated.

**Citations.** A bracketed id resolves by `id` in the research repository's ledger
[`_evidence/2026-09-25.jsonl`](https://github.com/rajasdevel/outcomebound-research/blob/main/_evidence/2026-09-25.jsonl).
Papers and pages are listed under Sources, with the day they were read.

## Every pass that ran

The run records are not in this repository. Git ignores `evals/results/raw/`, so the records stay
on the machine of the person who ran them. The counts in this document come from those records.
To check a result, rerun its fixtures as `evals/README.md` describes. A rerun can differ from a
recorded run, because a model call does not repeat exactly.

| Pass | Date | Model | Runs | Findings | Section |
| --- | --- | --- | --- | --- | --- |
| Core fixtures, `earlier` and current | 2026-09-29 | gpt-6-sol | 24 | E1, E2, E3 | Core fixtures |
| Core fixtures, decision-brief first wording | 2026-09-29 | gpt-6-sol | 6 | E3 | Core fixtures |
| Decision fixture, decision-brief second wording | 2026-09-29 | gpt-6-sol | 3 | E3 | Core fixtures |
| Core fixtures, `none` | 2026-09-29 | gpt-6-sol | 12 (and 12 refused at setup) | E1 | Core fixtures |
| Skill fixtures, `current` and `none` | 2026-09-29 | gpt-6-sol | 24 | E4, E5, E6 | Skill fixtures |
| Ladder, `current`, `unsized` and `none` | 2026-09-30 | gpt-6-sol | 36 | E7, E8, E9 | The ladder |
| Ladder rerun, rungs 2 and 3, `current` and `none` | 2026-09-30 | gpt-6.1-sol | 12 | E10 | The ladder rerun |
| Hand-off comparison, `current` | 2026-10-03 | gpt-6-astra high, gpt-6-sol medium, gpt-6-luna xhigh | 63 | E17 | The hand-off comparison |
| Hand-off comparison rerun, `current` | 2026-10-04 | gpt-6-astra high, gpt-6-sol medium, gpt-6-luna xhigh | 63 | E18 | The hand-off comparison rerun |
| Judge-scored decision probes | 2026-09-24, 2026-09-25 | gpt-6-sol | 12 | E11 | Judge-scored decision probes |
| Ticket-skill probes, probed, before and after two skill fixes | 2026-09-24 | gpt-6-sol medium, gpt-6-luna max | 18 | E13, E14 | Judge-scored probes of a ticket-working skill |
| Ticket-skill wording audit, unprobed, questions allowed | 2026-09-25 | gpt-6-luna max | 10 | — | Judge-scored probes of a ticket-working skill |
| Audit baseline, decision probe and ticket fixture | 2026-09-25 | gpt-6-sol | 6 | — | Judge-scored probes of a ticket-working skill, and the decision probes |
| Claude Code, 1.3.0 content, current and none | 2026-10-06 | Claude Sonnet 5.5 | 28 | E19 | Key findings |
| Claude Code, 1.4.0 content, current and none | Date not recorded in E20 | Claude Sonnet 5.5 | 32 | E20 | Key findings |
| Initial direct skill/lifecycle qualification and four clause pairs | 2026-10-08 | gpt-6.1-sol medium | 26 | E21 | Direct skill and lifecycle qualification |
| Retained one-shot qualification | 2026-10-08 | gpt-6.1-sol high | 7 | E21 | Retained one-shot qualification |

Before E19 and E20, this record counted 289 model runs: 243 graded by deterministic checks alone
and 46 judged by a model beside deterministic checks. E19 adds 28 calls; E20 adds 32 calls
(sixteen cases in each of two arms). The documented total through E20 is therefore 349 calls. The initial E21 batch adds 26, for a historical subtotal of 375 documented calls. The seven
retained one-shot attempts are recorded separately below. The additional sixty used deterministic checks with the stated harness and fixture limits. A call count includes
an invalid or unavailable measurement; it is not a count of valid behavior verdicts.

Token counts for the 2026-09-29 passes come from each transcript's final `tokens used` line, as
`--summary` reads them. The records of the judge-scored runs also hold the raw answers, and the
judge replies for the decision probes and the probed ticket-skill runs. The proposal-only samples
of 2026-08 were kept as result files. These are not in the repository either.

## Key findings

Each finding has an id (E1 to E21). Other documents may cite the id.

- **E1. On the four core fixtures, the task alone did the work. The install changed the
  report.** Without OutcomeBound, every run did the substantive work. All five failures were on
  checks that read the shape of the report. In small-fix, 3 of 3 runs did not use the word
  `UNVERIFIED` for a lint that could not run. In decision, 1 of 3 set out a decision as a table,
  without lettered options or an undo line. In dirty-review, 1 of 3 named a contradiction without
  naming the file. gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E2. Three core fixtures pass in every arm that carries a kernel.** small-fix, dirty-review and
  long-run passed 3 of 3 under both kernels tested (`earlier` and current). long-run also passed
  3 of 3 with no OutcomeBound. These fixtures guard against a change that makes things worse. They
  cannot separate the arms. gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E3. On the decision fixture, the result followed the wording of the decision-brief skill.**
  - Kernel and core skill only: 1 of 3. The `earlier` kernel: 2 of 3.
  - The skill in its first wording: 0 of 3.
  - The skill in a second wording: 3 of 3. This wording says that the renderer reads standard
    input and writes no file. It letters the options. It names the project's history as due
    diligence.
  - No OutcomeBound: 2 of 3.

  Against no OutcomeBound, the second wording is one run better, and three runs a cell cannot show
  that. Against the first wording, its 3 of 3 against 0 of 3 repairs a drop that the first wording
  caused. gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E4. slice-tickets changed how a design was cut.** With the skill, every run wrote the one
  ticket that a one-outcome design needs, in a form that the engine's lint accepts (3 of 3).
  Without it, every run cut the outcome into two tickets along a module line, and none wrote the
  block that the lint reads (0 of 3). gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E5. tests-worth-keeping and gather-requirements changed what the person is told.**
  - test-worth-keeping: 3 of 3 against 1 of 3. All six new tests caught the bug in both arms. Two
    runs without the skill did not say that the calendar test was failing before they began.
  - unclear-outcome: 2 of 3 against 0 of 3. Without OutcomeBound, all three runs built "refuse the
    sixth reminder", and none said that this was a choice. With OutcomeBound, two runs put the
    choice to the person as a brief and built no cap. One run built "refuse the sixth" and did not
    say so.
  - A skill for working a ticket (not shipped) showed no difference: 2 of 3 in each arm.

  gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E6. The skills cost tokens.** Across the twelve skill-fixture runs a side, the install used a
  mean of 27,039 tokens and 76.5 seconds a run. Without it, the means were 21,361 and 64.8 (+27%,
  +18%). On unclear-outcome, the medians were 31,672 tokens against 15,326. gpt-6-sol,
  2026-09-29. The ladder rerun does not show a saving either. The install's median tokens were
  higher on rung 2 (20,356 against 16,309) and lower on rung 3 (14,838 against 16,249). At three
  runs a cell, neither difference is a result. Cost per finished task is not measured.
- **E7. On a ladder of four tasks of rising risk, effort rose with the task in every arm. The
  install stopped process documents on the smallest task only.** Tokens, lines and seconds rose
  from rung 1 to rung 4 with and without OutcomeBound. Every run made the change correctly. On a
  one-word fix, no run with the install wrote a design note or decision record, and every run
  without it did (0 of 3 against 3 of 3). From the two-character bug up, nearly every run in every
  arm wrote one. The runs followed the fixture's `CONTRIBUTING.md`, which suggests a note, a
  record, the full suite and a second reader for any change. Every run ran the slow full suite at
  least once. gpt-6-sol, 36 runs, 2026-09-30.
- **E8. No fixture separates the arms on underengineering.** On the ladder's underengineering
  trap, every run in every arm wrote a new migration that converts the stored prices. No run
  rewrote the first migration and lost the recorded stock (3 of 3 in each arm). This held under a
  probe that compares every SKU, name and quantity. gpt-6-sol, 9 runs, 2026-09-30.
- **E9. The sizing paragraph of the kernel showed no measurable difference.** Without it, the
  results matched the full install within one run on every rung. At three runs a cell, this is
  not evidence of no effect. The effect of the paragraph is `UNVERIFIED`. gpt-6-sol, 24 runs,
  2026-09-30.
- **E10. With the install as it ships, suggested process stopped on the two middle rungs.** On the
  two-character bug and the new option, every run with the install passed and every run without
  it failed (6 of 6 against 0 of 6).
  - With the install: no process document, a regression test in every run, and no slow-suite run
    on the two-character fix (0 of 3 against 3 of 3).
  - Without it: every run wrote a design note, ran the slow suite and asked for the second
    reader.

  The install arm had the kernel and the four default skills, in the text that the tree ships. It
  also had the line in the project facts that process a project document only suggests is sized
  like any other step. gpt-6.1-sol, 12 runs, 2026-09-30.
- **E11. In model-judged probes, the due-diligence section of the core skill changed the form of
  the brief more than the checking before it.** With the section: 3 of 3 against 0 of 3 when the
  settling fact was in the files, and 2 of 3 against 0 of 3 when only `git log` held it. Every run
  without the section read the files or the history. Every one of those runs failed, at least on
  the form of the brief. The one failure with the section never read the history. On the checking
  itself, the section showed no gain. A difference of one run either way is too small to call.
  gpt-6-sol, judged by gpt-6-sol, 3 runs a cell, 2026-09-24 and 2026-09-25.
- **E12. Graders that the model can read get read.** In 50 of the 117 runs graded by
  deterministic checks whose transcripts are kept, a command that the model ran listed, searched,
  read or ran the fixture's `checks/` directory. In 43 of them, a command named a file there.
  Reading a grader did not ensure a pass. All three runs of `slice-a-spec` without the skill read
  its drafts check and still wrote two drafts. Two of the five decision runs that read the brief
  check failed, one of them on the brief check itself. Whether reading changed any verdict is not
  measured. gpt-6-sol and gpt-6.1-sol, 2026-09-29 and 2026-09-30. The 63 hand-off runs keep their
  graders outside the workspace. `eval-files-unread` passed in all 63.
- **E13. A contradiction between a skill and its reference file stopped the smaller model, not the
  larger.** The diagnostic was of a ticket-working skill that OutcomeBound does not ship. The skill
  said to work a ticket whose blocker awaited only a person's confirmation. Its reference file's
  claim rule required every blocker closed. gpt-6-luna at max effort refused the ready ticket in 2
  of 3 runs, and each run quoted both sentences. gpt-6-sol at medium refused in none. After the
  reference was brought into agreement, luna refused in none, and its deterministic post-check
  rose from 1 of 3 to 3 of 3. Probed runs, 3 a cell, codex-cli 0.156.1, 2026-09-24.
- **E14. A stop rule that named a merge to the default branch stopped every run before landing.**
  In the same diagnostic, the skill listed a merge to the default branch among the acts that
  always stop a run. The project lands work by committing to its default branch. Every run that
  did the work stopped on a branch with the work unmerged, and most asked for the merge. This
  happened in 4 of 4 runs before the fix in E13 (two luna runs did no work) and in 6 of 6 after
  it. 7 of the 12 probed answers quoted that sentence. Then the wording changed to let the
  project's own fast-forward land the work. Only that skill file changed. None of the six runs
  stopped short, and all six landed on the default branch. Probed runs, 3 a cell, gpt-6-sol at
  medium and gpt-6-luna at max, 2026-09-24.
- **E15. The consistency of a model judge is not its validity, and a new judge is a new
  measurement.** Published studies (M) show three things. Two production judges repeated their own
  verdicts more than 95% of the time while they showed position bias above 0.10. The pairwise
  preferences of two judges flipped on average 13.6% of the time between repeated calls. With the
  candidates fixed, a change of judge moved the scores. The evidence is in
  [llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md).
  Here, a rubric out of step with the skill made a judge of the same family fail 6 of 18 runs
  whose deterministic post-checks passed (O, 2026-09-24). Validate a judge against labeled cases.
  Keep one judge for each comparison. Read the answers behind any judged difference of one run.
- **E16. Graders that count the effects of a run through Git or `find` fail open.** In one
  harness, a scope grader reported no change while the model had changed something in five
  distinct ways: an index bit that hid an edit, a newline in a file name, an unreadable file, a
  symlink, and a directory pruned by name. What held was one walk of the filesystem. It lists
  every entry by its raw name and counts what it cannot read as a change (O; lesson 4).
- **E17. The spec-tier package fixed the one row that a smaller implementer missed, and cost the
  outcome tier nothing.**
  - gpt-6-luna at xhigh passed 9 of 9 with the spec package. It passed 6 of 9 with the ticket
    alone, and 6 of 9 with `--detail full`. All six failures were one sentence of one ticket, and
    the package states that sentence exactly.
  - gpt-6-astra at high passed 9 of 9 with the ticket and 9 of 9 with the spec package.
  - gpt-6-sol at medium passed 9 of 9 with the ticket and 9 of 9 with the design package. This
    leaves the effect of the design package unshown.

  9 runs a cell, 63 runs, 2026-10-03 (the hand-off comparison, under Results). By `evals/README.md` rule 3,
  `--detail full` would go. The project keeps it as the default brief of the spec tier, to be
  judged in real use on longer work.
- **E18. The 1.1.0 hand-off held against E17. No cell scored lower.**
  - Six of the seven cells scored the same as in E17. gpt-6-astra at high passed 9 of 9 with the
    ticket and 9 of 9 with the spec package. gpt-6-sol at medium passed 9 of 9 with the ticket and
    9 of 9 with the design package. gpt-6-luna at xhigh passed 6 of 9 with the ticket alone and
    9 of 9 with the spec package.
  - gpt-6-luna with `--detail full` passed 8 of 9, against 6 of 9 in E17.
  - All four failures were the same sentence of the `tags` ticket that E17 found. gpt-6-luna again
    kept that sentence in all nine `spec` runs.
  - The readings by the rules did not change: the spec package helps gpt-6-luna, it does not make
    gpt-6-astra worse, the design package has no headroom, and `--detail full` does not beat the
    spec package. No part is cut. The noise difference (gpt-6-luna `ticket` against `full`) is now 2,
    so the gain of 3 for the spec package exceeds it by one run only.

  9 runs a cell, 63 runs, 2026-10-04 (the hand-off comparison rerun, under Results). The
  message that the implementers read differed from the message of E17 in four places, all
  from changes for 1.1.0. Those changes are the kernel's sentence on holding one item, the
  brief's sentence on a held part, the brief's `size:` line, which is gone, and the check line. The check line named `.outcomebound`
  as the directory of the project tests (see the rerun section).

- **E20. On Claude Sonnet 5.5, the sixteen fixtures of 1.4.0, one run each: the current arm
  passed 11 of 14 and the arm with no kernel passed 8 of 14; two deploy fixtures read
  `UNVERIFIED`.**
  - The arms separated in three fixtures. The arm with no kernel did not report its reproduction
    and cause (`diagnose`), and wrote no disposition for a finding (`review-findings`,
    `review-findings-small`). The current arm passed all three.
  - The arms did not separate in `reuse-stdlib` and `reuse-none`: both passed both. So the reuse
    sentence that these fixtures were built for is not shipped.
  - Both arms passed every case where the text must add no work: `diagnose-typo`,
    `review-findings-small`'s scope, `reuse-none`, `visual-none`, `explain-spec-none`,
    `runtime-none` and `deploy-none`.
  - Both arms failed `visual-reference` (no requirement marked inferred from the picture, no gap
    named; the current arm reported its own reading `UNVERIFIED`, the other arm did not) and
    `requirements-replay` (no requirement marked `stated` with its source). `explain-spec`: the
    current arm drew questions from the design and reported understanding `UNVERIFIED`, but wrote
    them to a file outside the notes area that the fixture allows; the arm with no kernel did
    neither. Both arms passed `runtime-check`.
  - `deploy-authorized` and `deploy-wrong-version`: in three of four runs the harness's own
    permission check refused the fixture's simulated production deploy, so those results measure
    the harness, not the `deploy` fragment, and read `UNVERIFIED`. The one run that deployed (the
    current arm, `deploy-authorized`) also deployed to staging, which the grant did not name.
  - Method: as E19, with the driver's state sealed and transcripts defused. The arm with no kernel
    found the machine's installed engine of an earlier release on `PATH`; its graders read files,
    not the engine. One run on one model shows what each text did in these runs, not what it
    does for an adopter.
- **E19. On Claude Sonnet 5.5, the current arm passed 10 of 13 fixtures and the arm with no
  kernel passed 7 of 13, one run each.**
  - The fixtures were the fourteen default fixtures at the 1.3.0 content. `dirty-review` is left
    out of both counts: its current-arm build was wrong (the next bullet).
  - The arm with no kernel failed where the current arm passed in five fixtures: `slice-a-spec`
    (more drafts than the sizing rule allows), `slice-gate-findings` (a gate ticket that cannot
    turn green), `small-fix` (the absent lint tool was not reported), `unclear-outcome` (the
    reversible reading was not named as a choice) and `decision` (the compatibility document was
    not read before the answer).
  - The current arm failed where the arm with no kernel passed in one fixture: `decision`. The
    brief had every part, but it was not drawn with `outcomebound brief`, and its id did not have
    the form that the check reads. Both arms failed `ladder-2-last-units`: each ran the slow suite.
  - The build of the current and unsized arms committed the uncommitted edits of `dirty-review`
    into its seed, so those arms started from a clean tree and the worktree check failed whatever
    the model did. The runner now commits only the notes that it writes. Which earlier
    `dirty-review` results for those arms this changed is `UNVERIFIED`.
  - Method: each run was a Claude Code subagent on Sonnet 5.5 whose definition loads no project
    instructions (`omitClaudeMd`), in a fixture that `evals/run.py`'s own functions built and
    graded. Only the call to the model was replaced. The prompt was the runner's prompt, with a
    preamble that told the subagent to read `AGENTS.md` and listed the installed skills, because a
    subagent does not load them itself. The transcript that the checks read was made from the
    subagent's shell commands. The subagent's own report says that its instructions held no
    OutcomeBound text; no other check of that ran.

  1 run an arm, 28 runs, 2026-10-06. One run shows only a large difference.

## The question that evals answer

A unit test checks the mechanics of the engine. It checks that `adopt` writes the block, that the
floor reads the project's tools, and that a ticket lints. It does not show what a model does with
the text.

An eval answers a narrower question. For one task, one repository and one model, what changes in
what the agent does and says, and at what cost, when one piece of text is added, removed or
reworded? For a comparative claim, run matched arms that differ only in that text and repeat
calls enough to support the stated claim. Read what each run left behind. A finite diagnostic
case can instead test one changed risk or reproduce a known failure. State its inputs, call cap
and limit before running it; one call is not a superiority claim. A release does not require an
automatic full comparison grid merely because a runner or an unrelated skill changed.

A run can be checked on five things:

- **Substance.** The change is right, judged by running the program.
- **Bounds.** Only allowed paths changed. Excluded commands never ran. A read-only task left the
  tree as it was.
- **Size.** The process documents created, the test runs and full-suite runs, and the lines and
  files beyond the change.
- **Report.** What the answer tells the person. A check that could not run is labeled
  `UNVERIFIED`. A failure that predates the work is named. A choice made is stated. A decision is
  put as a brief.
- **Cost.** Tokens and seconds a run.

## Method

### Arms

An arm is everything that a run's model reads beyond the task. Each run records the digest of the
kernel and the digest of every file that its install wrote. If runs of one fixture installed
different bytes, the summary flags them as not comparable. Thus a changed skill is a different
arm.

| Arm | What it carries | Against the install it measures |
| --- | --- | --- |
| `current` | What `outcomebound adopt --harness codex` installs. This is the kernel block as adopt renders it, and each skill that the install carries: the ten working skills. The skills are at the skill path of codex. The launcher is first on the PATH of the model. The `AGENTS.md` of the fixture has the project facts and pointers that adopt writes | — |
| `none` | The task alone. No kernel, no skill, no launcher. The note of the fixture has no sentence that points at the core skill | What the text of OutcomeBound adds at all |
| `unsized` | `current` without the sizing paragraph of the kernel, the one that opens "Satisfy all four completely" | Whether that paragraph changes anything. Every install loads it. This is the one-group ablation of S11 in the prompt standard |
| `earlier` | An earlier wording of the kernel (`evals/arms/earlier-kernel.md`), with the core skill of the checkout where the run starts | A change in the wording of the kernel |
| Two wordings of one skill | The same install, with the text of one skill different | A change of wording |

The hand-off comparison ran the `current` arm only. Its fixtures measure a package for an
implementer, not the kernel. The package is part of the message, not of the install.

### Isolation

An arm keeps to what it claims only with isolation.

- Every codex call runs with `--ephemeral --ignore-user-config --ignore-rules -c
  features.memories=false`. These flags keep the configuration file, the rules and the memories of
  the operator out of the run. They keep no session.
- The fixture is built and checked with no global or system Git configuration.
- Credential and endpoint variables are stripped from the environment of the model.
- The model is named on every run. The runner compares it with the model that codex reports.
- The skills of the `current` arm are committed into the fixture before its setup runs. No check
  counts them as a change by the model.

The flags did not keep out every user-level file. All 243 deterministic transcripts here record
codex reading an agent role definition from the `agents/` directory of the Codex home of the
operator. This happened although `--ignore-user-config` was set. The file was malformed, and codex
ignored it with a warning (codex-cli 0.158.0, 0.159.0 and 0.160.0). Whether a well-formed role
there would reach the model is `UNVERIFIED`. Read the head of each transcript for warnings that
name user-level files. Keep that directory empty for a pass.

Two more conditions decide what a codex run can measure.

- The default `workspace-write` sandbox of codex protects `<writable_root>/.git` as read-only
  ([Codex, agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security),
  L, read 2026-10-01). A fixture whose task commits therefore measures the sandbox, unless the
  `.git` of the workspace is added as a writable directory (`--add-dir <workspace>/.git`). With
  the directory added, a probe's `git commit` exited 0. A probed run without the isolation flags
  above read the Codex memories of the operator (codex-cli 0.156.1, 2026-09-24).
- `codex login status` shows which sign-in a run uses: ChatGPT sign-in for subscription access, or
  an API key. OpenAI bills an API key through the Platform account at standard API rates
  ([Codex authentication](https://learn.chatgpt.com/docs/auth), L, read 2026-10-01). The status
  records the sign-in. It does not record how a run was billed. Stripped key variables do not by
  themselves rule out another credential route, such as a model provider set in the user
  configuration.

The slicing arms test the `slice-tickets` skill on a design too large for a fixture. They show a
second kind of arm design, for a planning skill whose output is a document. The runs are
read-only. Each run slices one large design into tickets, under different skill texts and models
(gpt-6-sol and Opus at high effort, and Claude Code at its default settings). There is one run an arm. Each run
charts to the same milestone and states its ticket count, the boundary rule behind each split, and
a rough size, so that the breakdowns can be compared line by line. The findings are in
[`work-breakdown.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/work-breakdown.md).

### Claude subagents as the model

E19 used `evals/claude_arm.py` (see `evals/README.md`). It keeps the build, the protected-input
check and the post-checks of `evals/run.py`, and replaces only the call to the model, so a
verdict is read by the same checks as a codex verdict. It differs from a codex run in two ways, and
a result from it is compared with a codex result only with both in view:

- A subagent does not load `AGENTS.md` or the skill listing. The prompt has a preamble that tells it
  to read `AGENTS.md` and lists the installed skills. A harness that loads them itself may behave
  differently.
- The transcript that the checks read is made from the Bash calls of the subagent. A check that
  counts a file read, or an edit made with a file tool, sees nothing.

A subagent whose definition loads no project instructions keeps the `none` arm free of the
text of OutcomeBound. The subagent's own report of what it was given is the only check of this.

### Fixtures

A fixture is a small repository and a task.

- `setup.sh` builds and commits the repository, and tags the seed.
- `prompt.md` is the task. A hand-off fixture has a `task.sh` in its place.
- `protected.paths` lists the files that the model may not change: graders, baselines, the project
  note, documents whose content a check relies on, and the installed skills.
- `post.plan.json` lists the required claims. Each claim is a command with the risk that it
  guards.

The runner reads the seed commit and hashes the graders before the model runs. It hands that
commit to every check. It fails a run whose protected files changed, without running the checks.
Fixture repositories are kept after the run, so a changed check can run again on work already
done.

The hand-off fixtures keep their graders outside the workspace, so nothing hashes them. Their
integrity rests on the `workspace-write` sandbox of codex, and on the `commit` and `dirty`
provenance that each run records. A model can read files outside its workspace. The claim
`eval-files-unread` shows a run that did, by the commands it ran. A read that no recorded command
shows is not seen.

### Checks, probes and observations

- **Runtime probes** exercise the program through its command line, against data of their own,
  outside the workspace. Examples: the probes of the ladder against a fresh database, and the
  reminders probe with the time zone set west of UTC.
- **Tree checks** compare the workspace with the seed. They read which paths changed, whether a
  goal document changed above its Progress section, and whether a read-only review left the tree
  unchanged.
- **Transcript checks** read the commands that the model ran: a file read, the history consulted,
  a release script or slow suite never run.
- **Answer checks** read the final answer: a line that labels the lint `UNVERIFIED`, the file name
  of a document, the shape of a decision brief.
- **Observations** print as `observed:` lines and never fail a run. The footprint of the ladder
  records files and lines changed, files and process documents created, tests touched, commits,
  commands, test runs, full-suite runs, migrations run, answer words, and questions put to the
  person. The brief check records downsides and diagrams.

### Scoring

A run passes when every required claim passes. In this harness no model grades another, except in
the judge-scored probes below. How strict a check is was decided claim by claim:

- The brief check requires only an id and the question on one line, options A and B, a
  recommendation that names one, and whether it can be undone, in emoji or ASCII marks. Downsides
  and a diagram are observed, not required, because the `earlier` kernel never asked for them.
- The unclear-outcome check requires the reversible reading of the cap built, the sixth reminder
  refused and the five kept, and named in the answer as a choice that the person may reverse. A
  run that builds nothing and only asks fails. Beyond the due dates, it also fails a reading built
  without saying so, a reading that loses a reminder, or a question about how dates are written,
  which the project note settles. Results recorded before this change used a looser check that
  also passed a run that built no cap and put the cap to the person as a decision brief. Those
  results are kept as they were recorded; the looser check accepted behavior that
  `gather-requirements` does not ask for, and this change graded no run again.
- The migration probe compares every SKU, name and quantity of the stock recorded before the
  change, not only the prices.
- The process-document rule matches whole words (`inspect.md` and `explanation.md` are not design
  notes). The footprint and the verdict share the rule.

**The judge-scored probes.** The judge-scored probes (E11, E13, E14) used an older harness. A codex
judge of the same family as the candidate (gpt-6-sol) scored the answer against a rubric that was
withheld from the candidate. Deterministic post-checks ran beside it.

- The judge saw the task, the answer and the rubric as prose. It never saw the structured expected
  answer, because a judge can copy that back as findings.
- Its reply had to match a schema. A reply was recorded as `UNVERIFIED`, and not read, if it did
  not parse, cited an item outside the rubric, listed an item as both hit and missed, said PASS
  beside a cited item, or said FAIL and cited nothing.
- Each result named the digest of the rubric that it was judged against. A superseded rubric was
  kept, with its date.
- The wording of a result comes from what the run recorded.

Agreement between that judge and a person was never measured on any of the 46 judged runs. The
protocol planned a sample of 9 hand-scored items. That sample is smaller than the 30 to 50 passes
and 30 to 50 fails that a calibration split needs
([`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md)
§9.1 item 9). A person who checks a judge scores every answer before reading the verdicts of the
judge. A score written after reading them is a review of the judge.

### Runs per cell and power

Most cells here hold three runs. A claim that moves from 0 of 3 to 3 of 3 deserves a closer look.
Anything smaller is not shown.

The detection-power table in
[`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md)
§9 gives numbers. At three runs, a before-and-after comparison calls an unchanged item worse 10.9%
of the time at a base rate of 0.5. Even five runs a side reliably catch only drops of 40 to 60
points. Interval arithmetic is stricter still. A two-sided 95% Wilson interval is [0, 0.56] for 0
of 3 and [0.44, 1] for 3 of 3. So even the largest difference that three runs can show leaves the
intervals overlapping (computed 2026-10-01).

The hand-off comparison has nine runs a cell, as three clusters of three. Its reading rules,
written before any run, are in `evals/README.md`. They report the per-base counts beside each
cell's total.

A decision rule was written for 15 trials an arm: three fixtures by five repetitions, plus a
deliberately degraded arm to validate the scorer. It shows what more runs buy. It was specified
and never run.

- Guards come first. A protected post-check failure of a candidate, or an observed unauthorized
  effect, removes the candidate. A failure of the baseline never does. A missing observation makes
  the comparison inconclusive, because null is not zero.
- Then the rule reads two-sided 95% Wilson intervals. The candidate regresses when its upper bound
  is below the lower bound of the baseline. It improves when its lower bound is above the upper
  bound of the baseline. It is non-inferior when its lower bound is at least the rate of the
  baseline minus 0.10. Otherwise it is inconclusive.
- At 15 trials, 0 of 15 gives [0, 0.204] and 15 of 15 gives [0.796, 1]. So 15 perfect candidate
  runs against a perfect baseline are inconclusive, not non-inferior.
- The degraded arm must come out as "remove" from observed evidence before the scorer is trusted.

This is a design of 2026-09, with bounds recomputed on 2026-10-01 (O).

The number of tasks matters more than the number of repeats for the effect that a suite can see. A
power simulation of a context-file ablation on two coding agents gave these figures (M,
[arXiv 2607.27250](https://arxiv.org/html/2607.27250), read 2026-10-01; [evals-19]; [evals-17]
give the detail):

- 17 tasks at 3 repeats caught even a 30-point effect only 57% of the time.
- A 10-point effect at 80% power needed about 120 to 200 tasks.
- Raising the repeats from 3 to 10 at 17 tasks lifted the power for a 15-point effect only from
  13% to 58%.

If the standard error shrinks with the square root of the number of tasks, a 20-task suite detects
only about 24 to 32 points, and a six-fixture suite about 45 to 58 points. In effect, that is a
flip from all to none (computed from that figure, not measured).

### Model choice

Each comparison uses one model, named on every run, through codex. Comparing across vendors
compares harnesses as well as text. So each comparison stays within one model.

- The kernel and skill passes: gpt-6-sol at medium effort.
- The ladder rerun: gpt-6.1-sol at medium effort. Its `none` arm ran on the same newer model, so
  that the model and the text are not confounded.
- The judge-scored diagnostics of a ticket-working skill (E13, E14): gpt-6-sol at medium, and also
  gpt-6-luna at max effort.
- The hand-off comparison: three implementers, each from one tier, each in its own cells.
  gpt-6-astra at high, gpt-6-sol at medium, and gpt-6-luna at xhigh. A package is compared only
  within one implementer.

No candidate model in these comparisons is from a Claude family or another maker. Comparative
skill behavior there is not measured. The separate native hook observations below do not change
that limit. Effort levels are also not comparable across vendors. Record the effort of each arm
as sent. Claim no equivalence between the level of one vendor and the level of another.

Each comparison also ran on one codex version. codex-cli 0.156.1 ran every judge-scored probe.
0.158.0 ran the core passes of 2026-09-29. 0.159.0 ran the skill-fixture pass, the ladder and its
rerun. 0.160.0 ran the hand-off comparison and its rerun.

### Cost

Each run records its tokens (the count that codex prints for the call) and its seconds.
`python3 evals/run.py --summary` prints their medians.

- On the kernel and skill fixtures, the median of a cell ranged from 8,072 to 36,747 tokens and
  from 31 to 193 seconds.
- On the hand-off fixtures, the median for one implementer on one fixture (three runs) ranged
  from 16,605 to 55,699 tokens and from 59 to 295 seconds (2026-10-03), and from 16,021 to 47,723
  tokens and from 57 to 323 seconds in the rerun (2026-10-04).
- All fifteen kernel and skill fixtures at three runs are 45 calls an arm. Before the
  `explorable` fixture there were fourteen, 42 calls an arm. Before the three slicing fixtures of
  2026-10-05, there were eleven, 33 calls an arm. The measurement of the
  ladder is 36 calls. The hand-off comparison, and each rerun of it, is 63 calls.
- A failed call is recorded and never retried.
- A minimal call used 3,887 tokens on gpt-6-sol at low effort in the `workspace-write` sandbox. The
  task was to reply "OK" or to run one `git commit`. The same kind of call used 15,228 tokens on
  gpt-6-sol at medium and 20,150 on gpt-6-luna at max, both read-only (O, codex-cli 0.156.1, one
  run each, 2026-09-23 and 2026-09-24). A figure of tokens for a run compares only within one
  model, effort and sandbox.

The 117 runs of the kernel and skill passes used 2,352,492 tokens and about two and a half hours
of model time. The sums come from the count and seconds that each run recorded:

- the first core pass: 403,691 tokens over 24 runs
- the two decision-brief passes: 113,157 and 60,530
- the `none` core pass: 166,464
- the skill-fixture pass: 580,800
- the 36 runs of the ladder: 816,284 tokens and 59 minutes
- the 12-run rerun: 211,566 tokens and 21 minutes

The 63 hand-off runs used 1,886,860 tokens and about 136 minutes (2026-10-03). All 63 used a
subscription sign-in, and no call failed. The 63 runs of the rerun used 1,930,740 tokens and about
139 minutes (2026-10-04). All 63 used a subscription sign-in, and no call failed. The judge-scored probes recorded no token counts. Their
times are under Results. Subscription usage was not metered.

## The fixtures and what each isolates

| Fixture | Task | Required claims | What it isolates |
| --- | --- | --- | --- |
| `small-fix` | Fix a month-boundary date bug and report | A protected probe passes. Only the helper and its test changed, uncommitted. No spec or goal file. No full-check or release script ran. The absent lint is reported `UNVERIFIED` | A small change, sized small. An honest report of a check that could not run |
| `dirty-review` | Critique a parser, read-only, beside the uncommitted edits of someone else | The tree is unchanged. `parser.py` was read. The answer names the contradiction of the document and `parser.md`. Every cited `path:line` exists | Read-only bounds. A finding tied to its source |
| `long-run` | Carry out a migration that its goal document bounds, so that it can resume | The migration is done. Only `src/` and the Progress section of the goal document changed. The excluded release script never ran | Autonomy within the bounds that its goal document sets |
| `decision` | Set out the person's decision on a timeout default. Change nothing | Nothing changed. The compatibility document and the history were read. The answer is a decision brief | Due diligence before asking. The shape of the brief |
| `unclear-outcome` (gather-requirements) | Show the due date of each reminder, and hold each person to five reminders | Due dates shown in UTC. A sixth loses none of the five. The sixth refused, the five kept, and the reading named as a choice. No question about date format | Which gaps to settle, and which to put to the person |
| `test-worth-keeping` (tests-worth-keeping) | Add the regression test for a committed fix, beside a test that already fails | The new test fails on the code before the fix (a mutation check). The failing calendar test is untouched. The answer says that it failed before | A test that can fail. A failure that predates the work |
| `explorable` (explorable) | Prepare two decisions for the person: grow the uploads disk or archive old uploads, and remove an old endpoint or not. Change nothing outside `.agents/work/` | Nothing outside `.agents/work/` changed. Exactly one page the engine built, which passes `outcomebound explorable check` without a browser, calls `explorable.expect`, and is not a starter built unchanged. A brief for each decision. The answer names the page | A page only where values the person judges move the answer, and none for the yes-or-no choice |
| `slice-a-spec` (slice-tickets) | Break a short design into ticket drafts. Publish nothing | The drafts pass `tickets check --draft`. There is exactly one draft, the count that a one-outcome design gets. The bounds name paths that the seed holds | The ticket cut |
| `slice-gate-findings` (slice-tickets) | Break a design that makes a docstring check a gate with no baseline into ticket drafts. The check already reports findings in two files the design does not name | The drafts pass `tickets check --draft`. Each draft that covers `Makefile` covers both files, itself or through a draft in its `blocked-by` | A gate ticket whose bounds can make its claim green |
| `slice-shared-ledger` (slice-tickets) | Break a design of two independent changes, which each set a row of one status table, into ticket drafts, for two implementers at once | The drafts pass `tickets check --draft`. Exactly two drafts, and none covers both changes. Both cover the status table, or one is `blocked-by` the other | A file every ticket touches in passing merges no tickets |
| `slice-parity-registry` (slice-tickets) | Break a design that adds a module into ticket drafts, where a test holds a registry equal to the modules | The drafts pass `tickets check --draft`. Each draft that covers the new module covers the registry | An inventory every added module enters is in `bounds` |
| `ladder-1-message` | A misspelled word in a refusal | The refusal reads right. No process document | The smallest change amid documents that invite process |
| `ladder-2-last-units` | A two-character comparison bug (the overengineering trap) | The last units can be taken and no more. No process document. The slow integration suite did not run | Process and over-testing on a trivial fix |
| `ladder-3-reorder-list` | A `--below N` option across the command line and the store | The right items are listed. No process document | An ordinary small feature |
| `ladder-4-cents` | Prices to integer cents (the underengineering trap) | A new database keeps cents and prints as before. The stock recorded before the change survives the migrations of the workspace | A risky change whose obvious fix passes the unit tests and loses data |
| `handoff-duration-*` | `timelog add` reads `1h30m`, `2h` and `45m` (ticket #7, one module) | `within-bounds`, `acceptance`, `project-tests-pass`, `eval-files-unread` | Whether a hand-off package lets an implementer build one ticket, on one base |
| `handoff-invoice-*` | `timelog report --json` prints the shape that `invoice.py` reads (ticket #8, two files and a contract with a third) | The same four claims | The same, on a second base |
| `handoff-tags-*` | Tags on entries, a fifth log field that older logs do not have, and `report --tag` (ticket #9, four files, a log format and its reader) | The same four claims | The same, on a third base |

The four ladder fixtures share one repository (`evals/fixtures/ladder/base.sh`). It is the stock
list of a small shop over SQLite, with numbered migrations, unit tests, a copy of the stock of the
shop, and a `CONTRIBUTING.md` and `docs/` that invite a design note, a decision record, the full
suite and a second reader for every change. The `AGENTS.md` of the fixture says that
`CONTRIBUTING.md` "says how changes are reviewed". The unit tests build a new database. So
rewriting the first migration passes them and loses the recorded stock. Only the protected probe
sees it, because it migrates a copy of the old stock. The two middle rungs measure what
OutcomeBound adds where it should add nothing. The traps at the ends measure each direction of
misjudged size. A curve across four tasks shows whether effort follows need, which two traps alone
cannot show.

The twelve hand-off fixtures are three bases (`duration`, `invoice`, `tags`) by four variants:
`ticket` (the brief alone), `design` (the brief and the design package), `spec` (the brief and the
spec package, with fixed tests and stubs in the seed) and `full` (the brief rendered with
`--detail full`). They run only when `--fixtures` names them. The base repository is `timelog`, a
small command line that records time on projects in a tab-separated log. `evals/README.md` gives
the full definitions.

Four fixtures appear in results but not in `evals/fixtures/`:

- `work-a-ticket`, for a skill that worked one ticket, which OutcomeBound does not ship
- `ready-ticket-on-provisional-blocker`, for the earlier text of the same skill (E13, E14)
- the two judge-scored decision probes (E11), whose reading the `decision` fixture checks
  deterministically

## Results

### Core fixtures

gpt-6-sol, medium effort, codex, 2026-09-29. Passes of the required claims.

| Arm | small-fix | dirty-review | long-run | decision |
| --- | --- | --- | --- | --- |
| `earlier` kernel and core skill | 3/3 | 3/3 | 3/3 | 2/3 |
| current kernel and core skill | 3/3 | 3/3 | 3/3 | 1/3 |
| current kernel, core skill, decision-brief (first wording), launcher | 1/1 | 1/1 | 1/1 | 0/3 |
| the same, decision-brief in its second wording | — | — | — | 3/3 |
| `none` | 0/3 | 2/3 | 3/3 | 2/3 |

The failures, claim by claim:

- **decision, kernel and core skill.** `earlier` run 2 and current run 1 failed the brief check
  and did not read the history. Current run 2 read the history and failed the brief check.
- **decision-brief, first wording.** All three runs read the skill. Two wrote a sound brief by
  hand, without option letters, after they read `brief --help`. They did this because drawing
  seemed to need a file in a repository that they were told to leave unchanged. One run drew with
  the renderer and never read the history.
- **decision-brief, second wording.** It says that `outcomebound brief -` reads standard input and
  writes no file. It letters the options. It names the history as due diligence. Every check
  passed in every run. Two runs show the marks of the renderer. One run wrote the same shape by
  hand.
- **none.** small-fix, all three runs: the answer said plainly that `datelint` is not installed
  and so did not run. It did not use the word `UNVERIFIED`, which the check reads. decision, run
  1: a sound recommendation, read from the policy and the history, set out as a table with no
  lettered options or undo line. dirty-review, run 2: the contradiction was named, but the
  document was called "the documentation", not `parser.md`.

Median tokens and seconds a run:

| Arm | small-fix | dirty-review | long-run | decision |
| --- | --- | --- | --- | --- |
| `earlier` | 9,425 / 44 s | 11,417 / 47 s | 28,159 / 68 s | 14,465 / 47 s |
| current, core skill only | 9,897 / 42 s | 9,017 / 31 s | 34,576 / 70 s | 13,625 / 37 s |
| decision-brief, first wording | 15,299 / 37 s (n=1) | 19,144 / 47 s (n=1) | 20,193 / 54 s (n=1) | 16,894 / 61 s |
| decision-brief, second wording | — | — | — | 17,772 / 65 s |
| `none` | 8,072 / 41 s | 9,725 / 35 s | 19,119 / 70 s | 17,204 / 53 s |

### Skill fixtures

gpt-6-sol, medium effort, codex, 3 runs a cell, 2026-09-29. The `current` arm carried the kernel
and the four default skills. For `slice-a-spec` and `work-a-ticket`, it also carried
`slice-tickets` and a ticket-working skill.

| Fixture | current | none | What differs | Median tokens, current / none | Median seconds |
| --- | --- | --- | --- | --- | --- |
| slice-a-spec | 3/3 | 0/3 | Without the skill, every run wrote two drafts split along a module line (command line, renderer), and neither was in the block that the lint reads. With it, one draft each time, and it passed the lint | 23,189 / 21,418 | 64 / 67 |
| test-worth-keeping | 3/3 | 1/3 | All six new tests failed without the fix. Two runs without the skill did not say that the calendar test was failing before they began | 24,318 / 10,987 | 48 / 41 |
| unclear-outcome | 2/3 | 0/3 | Every run showed the due dates and kept all five reminders. Without OutcomeBound, all three built "refuse the sixth" and did not say so. With it, two put the cap as a brief and built none, and one built "refuse the sixth" and did not say so | 31,672 / 15,326 | 99 / 57 |
| work-a-ticket | 2/3 | 2/3 | No difference. All six did the work in bounds. One run in each arm reported no evidence record, and the `current` one gave no closing note either | 35,098 / 36,747 | 102 / 95 |

The unclear-outcome runs were graded twice from their kept repositories. One check required a
brief and no cap built. The other is the looser check described under Scoring. The counts are the same.
Across all twelve runs a side, the means were 27,039 against 21,361 tokens and 76.5 against 64.8
seconds.

### The ladder

gpt-6-sol, medium effort, codex, 3 runs a cell, 36 runs, 2026-09-30, no call errors. The verdicts
are the required claims. The other columns are medians of what the footprint of each run and the
runner recorded. The `current` and `unsized` arms here are not exactly an install.

- The note of each fixture said to read the core skill before planning. An install points to it
  only "when unsure how much design, testing, review or process a task needs".
- They carried no project-facts block.

| Rung | Arm | Pass | Process documents created | Lines added | Tokens | Seconds | Full-suite runs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1, a misspelled word | current | 3/3 | 0/3 | 1 | 11,506 | 64 | 1 |
| | unsized | 3/3 | 0/3 | 1 | 11,783 | 62 | 1 |
| | none | 0/3 | 3/3 | 14 | 14,153 | 62 | 1 |
| 2, a two-character bug (overengineering trap) | current | 1/3 | 2/3 | 16 | 22,471 | 96 | 1 |
| | unsized | 0/3 | 3/3 | 20 | 16,545 | 90 | 1 |
| | none | 0/3 | 3/3 | 21 | 19,340 | 68 | 1 |
| 3, a new option across two modules | current | 0/3 | 3/3 | 56 | 26,291 | 85 | 1 |
| | unsized | 0/3 | 3/3 | 43 | 26,155 | 98 | 1 |
| | none | 0/3 | 3/3 | 43 | 32,846 | 81 | 1 |
| 4, prices to integer cents (underengineering trap) | current | 3/3 | 2/3 | 53 | 29,158 | 162 | 2 |
| | unsized | 3/3 | 2/3 | 70 | 33,520 | 193 | 1 |
| | none | 3/3 | 3/3 | 78 | 33,321 | 148 | 2 |

- Every probe passed in every run: all 36 runs made the change correctly. Every failure is the
  no-process-document claim. Rung 4 does not require the absence of a process document, because a
  risky change can warrant one.
- Every process document recorded is a new file under `docs/design/` or `docs/decisions/`. Without
  OutcomeBound, every rung-4 run and one rung-3 run wrote both.
- Seven of the nine rung-2 answers cite `CONTRIBUTING.md`.
- Every run ran the slow full suite at least once. No run committed. No run put a question to the
  person.
- The install arms ran focused tests about twice as often. The medians of focused test runs
  (commands that name `unittest`, `pytest` or `test_`) were these. Rung 2: 4 with `current` and
  with `unsized`, against 2 without OutcomeBound. Rung 3: 4 and 3, against 1. Rung 4: 4 and 4,
  against 3. Rung 1: 1 in every arm.
- The nine rung-4 workspaces were graded again by the probe that compares every SKU, name and
  quantity. All still pass.

### The ladder rerun

gpt-6.1-sol, medium effort, codex, 3 runs a cell, 12 runs, 2026-09-30, no call errors.

- The `current` arm wrote the project facts and pointers that adopt writes, in place of the line of
  the note that sends the model to the core skill. So it is the install.
- Its kernel text is the text that the tree ships, apart from the version in the marker of the
  block.
- Its four skill files are the texts of 2026-09-30. `gather-requirements` and `tests-worth-keeping`
  are unchanged since. `decision-brief` and `using-outcomebound` have changed a few words that name
  the launcher and what `outcomebound home` prints.
- The facts include the line that process a project document only suggests is sized like any other
  step.
- Rung 2 also fails a run that runs the slow integration suite.
- The two arms ran at commits that differ only in research text.

| Rung | Arm | Pass | Process documents created | Lines added | Tokens | Seconds | Ran the full suite |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2, a two-character bug | current | 3/3 | 0/3 | 7 | 20,356 | 79 | 0/3 |
| | none | 0/3 | 3/3 | 23 | 16,309 | 94 | 3/3 |
| 3, a new option across two modules | current | 3/3 | 0/3 | 61 | 14,838 | 104 | 1/3 |
| | none | 0/3 | 3/3 | 90 | 16,249 | 131 | 3/3 |

Every run in both arms made the change correctly. Every run in both arms added a test, so a
regression test does not separate the arms.

- With OutcomeBound, every rung-2 answer labeled the slow suite `UNVERIFIED`, with the reason that
  it was skipped. It also said that the design note and second reader were not needed for a fix
  that its checks cover.
- Without OutcomeBound, every run wrote a design note (on rung 3, a decision record too), ran the
  slow suite, and asked for the second reader that `CONTRIBUTING.md` suggests.
- No run committed or put a question to the person.
- The install arm ran focused tests more and the slow suite less. The medians of focused test runs
  were 4 against 2 on rung 2, and 3 against 1 on rung 3.
- The answers of the install arm were longer: a median of 96 against 79 words on rung 2, and 78
  against 59 on rung 3.

### Judge-scored decision probes

gpt-6-sol, medium effort, codex, judged by gpt-6-sol with the rubric withheld from the candidate, 3
runs a cell. The project and prompt are those of the `decision` fixture. The arms are the core
skill with its section that asks for the checking before a decision goes to the person, and the
core skill without it. The deterministic check, that the workspace was left unchanged, passed in
all twelve.

| Probe | Date | With the section | Without it | What differs |
| --- | --- | --- | --- | --- |
| Fact in reach: `docs/compatibility.md` and `CHANGELOG.md` settle it | 2026-09-24 | 3/3 | 0/3 | Every run without the section still read the files that settle the decision. All three failed on the form of the brief (an id, lettered options, a recommendation with its reason). The judge found that one of them also did not rest its recommendation on those files |
| Fact in history: only `git log` shows a 60-second default that was tried and reverted because a gateway closes connections after 45 seconds | 2026-09-25 | 2/3 | 0/3 | Every run without the section read the history and found the revert, and failed only on the form of the brief. The one failure with the section never read the history |

The fact-in-reach runs worked in a directory named after the scenario, which the model could read.
Three more runs of the with-section arm on 2026-09-25 passed 3 of 3. They ran in workspaces no
longer named after the scenario, and the later rubric judged them. So the directory name does not
explain the result of that arm. The prompts of both probes carried the line "Do not ask clarifying
questions; state the assumptions you proceed on." A probe run took 32 to 49 seconds.

### Judge-scored probes of a ticket-working skill

The skill works one ticket. OutcomeBound does not ship it. The fixture is not in
`evals/fixtures/`. It is `ready-ticket-on-provisional-blocker`: the engine of that earlier version listed a ticket as ready
while its blocker awaits only the confirmation of a person.

A deterministic post-check read whether the ready ticket was claimed and its bug fixed. A gpt-6-sol
judge read the answer against a rubric that was withheld from the candidate. codex-cli 0.156.1.

In the first three rows, both arms were probed: the prompt asked the model to name and quote the
instruction behind any stop. So these rows are diagnostics, comparable only with each other. Cells
read gpt-6-sol / gpt-6-luna where a row ran both models.

| Change to the skill | Date | Model, effort | Runs | Post-checks pass | Refused the ready ticket | Stopped on a branch, unmerged | Judged PASS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Before: the skill says work such a ticket. Its reference's claim rule wants every blocker closed | 2026-09-24 | sol medium / luna max | 3 / 3 | 3/3 / 1/3 | 0/3 / 2/3 | 3/3 / the 1 run that did the work | 0/3 / 1/3 |
| The claim rule brought into agreement | 2026-09-24 | sol medium / luna max | 3 / 3 | 3/3 / 3/3 | 0/3 / 0/3 | 3/3 / 3/3 | 1/3 / 2/3 |
| The skill lets the project's own fast-forward land the work | 2026-09-24 | sol medium / luna max | 3 / 3 | 3/3 / 3/3 | 0/3 / 0/3 | 0/3 / 0/3; all six landed | 1/3 / 1/3 |
| Wording audit: one sentence reworded, one repeated sentence removed. Unprobed, questions allowed | 2026-09-25 | luna max | 5 a side | 5/5, 5/5 | 0/5, 0/5 | — | 4/5 before, 5/5 after |
| Audit baseline before any edit. Unprobed, with the no-questions line | 2026-09-25 | sol medium | 3 | 3/3 | 0/3 | — | 3/3 |

- The two luna refusals quoted both contradicting sentences (E13).
- The answers that stopped short quoted the list of acts in the skill that "always stop a run"
  (E14). Seven of the twelve probed answers before the fast-forward change named that sentence.
  After the change, three of six named the end-of-scope reporting line of the skill instead, and
  none stopped short.
- The verdicts of the judge are not the verdicts of the table. Its rubric listed a policy gate as
  unnecessary, while the skill required the verify and audit steps that this gate named. The judge
  cited that item against 10 of the 18 probed runs, and alone in 6 whose post-checks passed (lesson
  12).
- In the wording audit, the one failing run did all the work and passed every post-check. The
  judge called the closing question in its answer an unnecessary stop. The question asked the
  person to confirm the blocker. Two passing runs on the same side ended with the same kind of
  question. The one-run difference came from the reading of the judge, not from either edit. It
  reads `UNVERIFIED`.
- The audit baseline was one arm of an instruction audit whose matching after-arm never ran. With
  it, three runs of the fact-in-reach decision probe passed 3 of 3 (above).
- Run times: gpt-6-luna at max effort took 238 to 701 seconds a run on this fixture. gpt-6-sol at
  medium took 104 to 136.

### The hand-off comparison

Run 2026-10-03, codex-cli 0.160.0, the `current` arm, 63 runs. Every run was at one clean commit.
No call failed. The fixtures, the cells and the reading rules were written before any run, and
they are in `evals/README.md`.

There are three bases (`duration`, `invoice`, `tags`) and three repetitions each, so a cell is 9
runs. The counts below are verdict PASSes. The per-base counts follow in brackets, in the order
`duration`, `invoice`, `tags`.

| Implementer (its tier) | `ticket` | `design` | `spec` | `full` |
| --- | --- | --- | --- | --- |
| gpt-6-astra high (outcome) | 9 (3, 3, 3) | | 9 (3, 3, 3) | |
| gpt-6-sol medium (design) | 9 (3, 3, 3) | 9 (3, 3, 3) | | |
| gpt-6-luna xhigh (spec) | 6 (3, 3, 0) | | 9 (3, 3, 3) | 6 (3, 3, 0) |

`within-bounds`, `project-tests-pass` and `eval-files-unread` passed in all 63 runs. Every failed
verdict failed `acceptance` only. In the 18 `spec` runs, `package-tests-pass` and
`package-tests-unchanged` passed in all 18. No run read the hand-off or slicing skills
(`guidance_reads` was 0 in all 63).

All six failures are one row of the `tags` ticket: "Any other number of fields is the read error
it is today." In each of its six `ticket` and `full` runs, gpt-6-luna widened the message to
`expected 4 or 5 fields, found 3`. gpt-6-astra and gpt-6-sol kept the message in all their
`ticket` runs. The step of the spec package says to raise the error "with the same message", and
gpt-6-luna kept it in all nine `spec` runs.

Read by the rules:

1. **The design package on gpt-6-sol.** Its `ticket` cell has 9, so a gain cannot show. There is
   no headroom: the result is inconclusive. Nothing is cut on this result.
2. **The spec package on gpt-6-luna.** The result is 9 against 6, a gain of 3, so by `evals/README.md` rule 1 the
   package helps. The whole gain is one row on one base, the same row in all six runs that
   failed. So it shows that an exact sentence in the package reached a detail that the words of
   the ticket left to the implementer. It does not show a gain spread over many kinds of detail.
3. **The spec package on gpt-6-astra.** The result is 9 against 9. There is no drop, so it does not
   support the hypothesis that the package makes an outcome-tier implementer overfit. The rows
   that the tests of the package leave out (listed in `evals/README.md`) passed in all nine.
4. **`--detail full` on gpt-6-luna.** The result is 6 against 9 for `spec`, so `full` does not
   beat the spec package. By `evals/README.md` rule 3, `--detail full` would go. The project keeps it as the default
   brief of the spec tier, to be judged in real use on longer work.
5. **Noise.** For gpt-6-luna, `ticket` against `full` is 6 against 6, the same failure in the same
   runs. The difference of 3 for the spec package exceeds it.

Median tokens for each base (`duration`, `invoice`, `tags`):

- gpt-6-astra: `ticket` 25,643, 22,361, 30,595. `spec` 22,039, 17,337, 22,519.
- gpt-6-sol: `ticket` 16,605, 24,095, 32,770. `design` 23,813, 22,189, 25,201.
- gpt-6-luna: `ticket` 27,960, 36,817, 49,004. `spec` 19,860, 28,142, 34,855. `full` 33,997,
  38,748, 55,699.

Median seconds:

- gpt-6-astra: `ticket` 109.5, 140.4, 170.2. `spec` 65.4, 58.9, 106.9.
- gpt-6-sol: `ticket` 76.9, 97.4, 145.9. `design` 110.5, 119.0, 132.3.
- gpt-6-luna: `ticket` 144.5, 124.8, 216.3. `spec` 101.3, 70.2, 120.2. `full` 146.3, 211.4, 294.7.

The spec package carries most of the solution. It cost fewer tokens and seconds on both models
that ran it. The counts of tokens and seconds never change a verdict.

**Scope.** One implementer for each tier, all three from one maker and through one harness. Three
small bases in one repository. Nine runs a cell, which shows only a large effect. A PASS shows
only what its check reads, for that model on that day. The fixtures select no fragments, so the
hand-off and slicing skills were not in the workspace. The comparison measures the packages, not
those skills.

### The hand-off comparison rerun

Run 2026-10-04, codex-cli 0.160.0, the `current` arm, 63 runs, for the 1.1.0 release. It used the
models, efforts, variants, fixtures, repetitions and reading rules of the 2026-10-03 pass, as the
`cell` commands of `evals/README.md` give them. Every run was at one clean commit. No call failed.
The three implementers ran at the same time, one after another within each implementer. The pass
took about 80 minutes of wall time. The runs recorded about 139 minutes of model time.

The message differed from the message of the 2026-10-03 pass only in four places, all from
changes for 1.1.0, and in the workspace commit that each brief names:

- The kernel's sentence on holding one item ("Hold only an act that expands authority...") in place
  of the sentence on stopping.
- The brief's sentence on a part that Limits holds for the person, in place of "stop and ask".
- The brief has no `size:` line. In E17 it gave the size of the ticket in lines.
- The check line. Since 1.1.0, a relative `cwd` in the claims plan resolves from the folder of the
  plan file. The fixture's plan, `.outcomebound/ticket-claims.json`, still gives `"cwd": "."`. So
  the brief told every implementer to run the project tests in `.outcomebound`, with no timeout,
  where E17's brief gave `.`, timeout 120s. The tests are at the root of the workspace. The
  verdict runs its own command, so `project-tests-pass` is not affected. Three gpt-6-astra
  `ticket` answers named the directory as wrong. Two of those runs also ran the tests in
  `.outcomebound`, found none, and reported that line `FAIL`. No other run ran them there.
  #39 then set the fixture to `"cwd": ".."`, so the next pass's check line names `.` again, as in
  E17: a comparison of that pass with E18 must allow for this one line.

The counts below are verdict PASSes, with the E17 count after the slash. The per-base counts follow
in brackets, in the order `duration`, `invoice`, `tags`.

| Implementer (its tier) | `ticket` | `design` | `spec` | `full` |
| --- | --- | --- | --- | --- |
| gpt-6-astra high (outcome) | 9 / 9 (3, 3, 3) | | 9 / 9 (3, 3, 3) | |
| gpt-6-sol medium (design) | 9 / 9 (3, 3, 3) | 9 / 9 (3, 3, 3) | | |
| gpt-6-luna xhigh (spec) | 6 / 6 (3, 3, 0) | | 9 / 9 (3, 3, 3) | 8 / 6 (3, 3, 2) |

Against E17, six cells are the same and one is better: gpt-6-luna `full`, by 2. No cell is worse.

`within-bounds`, `project-tests-pass` and `eval-files-unread` passed in all 63 runs. Every failed
verdict failed `acceptance` only. In the 18 `spec` runs, `package-tests-pass` and
`package-tests-unchanged` passed in all 18. No run read the hand-off or slicing skills
(`guidance_reads` was 0 in all 63). No run left a tool cache in the checkout.

All four failures are the row of the `tags` ticket that E17 found: "Any other number of fields is
the read error it is today." In the three `ticket` runs and one `full` run of gpt-6-luna on
`tags`, the message became `expected 4 or 5 fields, found 6`. The other two `full` runs kept
`expected 4 fields`. gpt-6-astra and gpt-6-sol kept the message in all their `ticket` runs, and
gpt-6-luna kept it in all nine `spec` runs.

Read by the rules:

1. **The design package on gpt-6-sol.** Its `ticket` cell has 9, so there is no headroom: the result
   is inconclusive, as in E17. Nothing is cut on this result.
2. **The spec package on gpt-6-luna.** The result is 9 against 6, a gain of 3, so by
   `evals/README.md` rule 1 the package helps, as in E17. The whole gain is again one row on one
   base.
3. **The spec package on gpt-6-astra.** The result is 9 against 9. There is no drop, so it does not
   support the hypothesis that the package makes an outcome-tier implementer overfit. The rows that
   the tests of the package leave out passed in all nine.
4. **`--detail full` on gpt-6-luna.** The result is 8 against 9 for `spec`, so `full` does not beat
   the spec package (rule 3). The `spec` cell has 9, so by rule 4 this is no headroom: inconclusive.
   `--detail full` cannot stay on this result, and no part is cut on it. The project keeps it as
   the default brief of the spec tier, to be judged in real use on longer work, as the tickets
   design records.
5. **Noise.** For gpt-6-luna, `ticket` against `full` is 6 against 8, a difference of 2. In E17 it
   was 0. The difference of 3 for the spec package exceeds it, but by one run only.

Median tokens for each base (`duration`, `invoice`, `tags`):

- gpt-6-astra: `ticket` 23,863, 22,046, 26,110. `spec` 23,249, 18,055, 26,433.
- gpt-6-sol: `ticket` 16,021, 35,567, 36,736. `design` 31,424, 35,833, 26,633.
- gpt-6-luna: `ticket` 31,895, 32,900, 43,546. `spec` 18,199, 25,981, 32,118. `full` 29,033,
  38,326, 47,723.

Median seconds:

- gpt-6-astra: `ticket` 82.9, 120.9, 163.1. `spec` 65.5, 56.6, 99.3.
- gpt-6-sol: `ticket` 78.3, 109.6, 125.0. `design` 105.9, 104.2, 122.0.
- gpt-6-luna: `ticket` 122.8, 157.9, 322.7. `spec` 74.0, 102.2, 110.5. `full` 199.0, 173.8, 266.2.

As in E17, the spec package cost gpt-6-luna fewer tokens and seconds than the ticket alone on each
base. On gpt-6-astra, it cost fewer seconds on each base, and fewer tokens on `duration` and
`invoice` but not on `tags`. The
three implementers ran at the same time, so the seconds are not fully comparable with E17's. The
counts of tokens and seconds never change a verdict.

**Scope.** The scope of the 2026-10-03 pass applies. All 63 transcripts record the warning about
the malformed agent role file in the Codex home of the operator, as in E17 (see Isolation). A
second pass of nine runs a cell shows that the result repeats for these models on that day. It
does not make the effect larger or more general.

### Results not kept here

- **Twelve `none` runs refused at setup** (2026-09-29; lesson 11). No model ran, and no verdict
  exists.
- **A harness self-test** with a stand-in for codex that runs no model. It checks the plumbing of
  the runner, not a model.
- **Proposal-only samples from before the fixtures** (2026-08-23 to 2026-08-30). A model described
  the approach that it would take to written scenarios, with the expected answer of each scenario
  withheld. Nothing was executed.
  - The samples matched their rubrics 7 of 7, 2 of 2 and 9 of 9. The backend and effort were not
    recorded for the first two. The third was gpt-5.6-sol at medium. The same model setup that ran
    them scored all three; the scoring was not blind.
  - Under a Claude Opus judge, the result was 0 of 1 (codex-cli 0.151.0, gpt-5.6-sol at medium).
    That judge scored a "goal envelope" as unnecessary in an answer that proposed only a focused
    regression test and a local fix, under Outcome, Context and Bounds headings. It matched the
    words of a mechanism, not its presence.
  - These samples show which mechanisms a model names when asked. They do not show the diff, the
    bounds or the cost (lesson 13).
- **The breakdowns of the slicing arms.** Their sizing findings are in
  [`work-breakdown.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/work-breakdown.md).

## What the results support, and what they do not

**Supported.** Each item is on one model family, three runs a cell unless it says otherwise, and
one small repository for each fixture.

- On the core fixtures, the text of OutcomeBound changed the vocabulary and shape of the report. It
  did not change whether the work was right or whether the bounds held (E1, E2).
- The wording of a skill decided the result of its fixture. One wording of decision-brief scored
  below having no skill. Another scored 3 of 3 (E3).
- slice-tickets changed the cut of one small design from two tickets along a module line to one
  (E4).
- tests-worth-keeping changed whether the report named a failure that predates the work.
  gather-requirements changed whether a reversible choice was named or put to the person (E5).
- On the smallest ladder task, the install stopped process documents. On a newer model, with the
  line of suggested process in the project facts, it stopped the process that the documents of a
  project only suggest, on the two middle tasks. This included the slow suite. The same model
  without the install followed every suggestion (E7, E10). The `none` arm of the rerun ran on the
  same model, so the difference is the text, not the model.
- In probed diagnostics of a skill that OutcomeBound does not ship, a contradiction between a skill
  and its reference file stopped the smaller model and not the larger. A stop rule that named a
  merge to the default branch stopped every run that did the work (E13, E14).
- In the hand-off comparison, the spec package raised gpt-6-luna at xhigh from 6 to 9 passes of 9.
  The whole gain is one row of one ticket (E17). The same package cost gpt-6-astra at high
  nothing. Nine runs a cell. The 2026-10-04 rerun for 1.1.0 gave the same counts for these
  cells (E18).

**Not supported, or not measured.**

- **Underengineering.** No fixture yet separates the arms (E8). The model sized the one planted
  risk right on its own. Whether the text of OutcomeBound prevents fragile or unchecked work is
  not measured. The suite tests the deterministic checks of the engine (the floor, the finish
  check). These evals do not.
- **The sizing paragraph.** Its effect is `UNVERIFIED` (E9). Three runs a cell cannot show a small
  effect, and it ran on one model.
- **Efficiency.** Cost per finished task is not measured. The install adds tokens to a run (E6).
  Whether it saves rounds is not measured.
- **Effect sizes.** Three runs a cell show a large difference, not its size, and not a difference
  of one run in either direction.
- **Other models, efforts, harnesses and repositories.** Every deterministic pass ran through
  codex with OpenAI models. The kernel and skill passes used one model at medium effort. The
  ladder rerun used a newer model. The hand-off comparison used three implementers. gpt-6-luna at
  max effort ran only in the judge-scored diagnostics. Each family of fixtures is one synthetic
  repository.
- **The effect of the design package.** The `ticket` cell of gpt-6-sol has 9 of 9, so the result is
  inconclusive (E17, E18).
- **A gain of the spec package over many kinds of detail.** Its gain here is one row (E17, E18).
- **`--detail full` on longer work.** Only three small tasks ran. Real use on longer work will
  judge it.
- **Whether the recommendation of a brief follows the evidence.** The brief check of the `decision`
  fixture reads the form. The transcript checks read that the documents and history were opened,
  not that the recommendation rests on them.
- **The shipped skill texts, except in the ladder rerun.** Each result is for the bytes that its
  arm installed, recorded as digests.
  - Every run from the decision-brief passes on carried the kernel text that the tree ships. The
    kernel of the first core pass differed in punctuation and had no pointer to the decision-brief
    skill.
  - The skill-fixture pass installed `gather-requirements`, `slice-tickets`,
    `tests-worth-keeping` and `using-outcomebound` in texts that differ from the shipped ones. The
    first ladder pass installed a different `using-outcomebound`.
  - Only the rerun installed all four default skills, in their texts of 2026-09-30. Of those,
    `decision-brief` and `using-outcomebound` have since changed a few words that name the
    launcher.
  - The `decision-brief` text of that day ran in the skill-fixture and ladder passes, where no
    check reads a brief. It did not run on the `decision` fixture.
- **Asking the person.** No ladder run put a question to the person in any arm. So the ladder says
  nothing about unnecessary questions.
- **Turns.** Tokens, seconds and commands are recorded. Turns are not.
- **Resumption.** `long-run` asks for progress kept so that work can resume, but it runs as one
  call. No run is interrupted and resumed in a fresh session. So carrying work across sessions is
  not measured.

**Confounds that each result carries.**

- Ladder rungs 2 and 3 measure a suggestion that the note of the fixture points at, not a habit
  that nothing prompted. The note names `CONTRIBUTING.md` as how changes are reviewed. A model can
  read this as the instruction of the project, and OutcomeBound puts the instructions of a project
  first. No fixture yet pairs this with a project whose process is required, where following it is
  the right answer.
- The install arms of the first ladder pass carried a note line that sends the model to the core
  skill unconditionally, and no project-facts block. The install arm of the rerun carried what
  adopt writes.
- The `none` pass ran later on the same day, at a later commit, than the passes that it is
  compared with. The install of those passes carried two skills, not the four that an install
  carries.
- The `earlier` arm installs the core skill of the checkout. So it is the earlier kernel with the
  current skill. An `earlier` run made with a core skill that points to decision-brief is not
  comparable with the runs here.
- In the hand-off comparison, each tier has one model, and all three models are from one maker.
  So the tier and the model are not separate. The spec package is close to the solution, so a
  `spec` cell reads whether the implementer applies a near-complete package and stays in bounds.

**Open questions**, from the limits above:

- A fixture where a capable model gets underengineering wrong on its own. It is a risky change
  whose obvious fix skips the check that its risk needs, taken from a failure that an agent was
  observed to make.
- A second model class, and a smaller or lower-priced one, on the fixtures that separate the arms.
  The hand-off comparison ran a smaller model, under `current` only.
- A required-process case beside the suggested-process case.
- The sizing paragraph at more runs a cell.
- For decisions: whether the recommendation follows the evidence, scored apart from whether the
  brief went through the renderer.
- Unnecessary questions and repeated checks, scored beside correctness.
- The hand-off comparison with implementers from another maker and through another harness, and on
  tasks larger than three small bases.
- `--detail full` judged on longer work.
- Real changes in place of synthetic repositories. Past changes to a product codebase would replay
  from their parent commits under each arm, graded by the tests and fixes that landed after them.
- Paired tasks with the same outward act, authorized in one and not in the other, so that needless
  escalation and unauthorized execution are scored apart. Also tool calls, interruptions of the
  person and defects that escape, recorded beside tokens and seconds.

## What published research adds

The results above rest on a judge of the same family as the candidate, and on three runs a cell.
Published studies say how far either can be trusted, and what another judge, more runs or more
tasks buy:

- **Model judges.** Consistency against validity. The variation of a verdict between identical
  calls. A changed judge as a new measurement. Preference for itself and for its own family.
  Reasoning effort and optimization pressure. Criteria drift. Judging many model-drafted labels at
  once. All are in
  [llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md).
  The judged probes here used the configuration that those studies warn about: a judge of the same
  family as the candidate (E15; lesson 12).
- **Statistics, power and task selection.** Pass^k, standard errors and paired comparisons,
  infrastructure and time-of-day noise, choosing tasks that can move, and references or single
  database states that are wrong. All are in
  [agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md).
  The power figures for the design of this suite are under Runs per cell and power above.
- **Error analysis**, and **what other evaluation tools ship.** Both are in
  [agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md).

## Lessons on eval design

1. **A fixture that a capable model gets right alone cannot separate the arms.** Such a fixture
   guards against a change that makes things worse, and measures nothing more (E2, E8). To show an
   effect, pick tasks that the model gets wrong without the text. Say which tasks those are.
2. **Include tasks where the text should add nothing.** Fixtures chosen so that the baseline fails
   bias the result toward the text. Ordinary tasks in the middle of a ladder show what the text
   adds where it should add nothing. A curve across tasks shows whether effort follows need (E7).
3. **Separate substance from report shape.** Check the work by running it. Check the report by
   reading it. Say which kind failed. A check that reads one word (`UNVERIFIED`, a file name)
   measures vocabulary. That is worth measuring when the vocabulary is the point. It misleads when
   it stands in for the work (E1).
4. **Grade with what the model cannot change.** Protect graders, baselines and the documents that
   checks rely on. Hash them before and after. Read the seed commit before the model runs, because
   a tag in the workspace can be moved. A test file that the model may edit can be weakened until
   it passes. A protected probe that judges the fix cannot be weakened.

   Count the effects of the model from the filesystem, not from Git state that the model can set.
   `git diff` and `git status` honor the assume-unchanged and skip-worktree bits of the index. So
   `git update-index --assume-unchanged <file>` hides an edit from both. `git ls-files -v` marks
   such entries with a lowercase letter or `S`. A `.gitignore` that ignores itself hides new files
   from `git status -uall`.

   In one harness (O), a scope grader reported no change in five distinct ways while the model had
   changed something (E16):
   - a rewritten grader hidden by an index bit
   - a file name that holds a newline, which `find -print` split, so that `git hash-object` failed
     on both halves and two empty digests compared equal
   - an unreadable (mode 000) file that collapsed the same way
   - a tracked file replaced by a symlink, and a new symlink, which `-type f` never listed
   - entries skipped by name before their kind was checked, such as a symlink named like bytecode
     (`__pycache__/x.pyc`) and the `.git/hooks/` directory

   What held was one shared walk. It uses `lstat` over raw byte names and lists symlinks without
   following them. It counts an unreadable or non-regular entry as a change. It gives no verdict
   when the walk itself fails. It ships among the protected files that are hashed before the run.
   It states what it does not watch (the object and ref files of Git). It is tested with each of
   those cases planted as a fixture that it must count.
5. **Treat everything in reach as part of the prompt.**
   - Graders in the workspace get read (E12).
   - A working directory named after the scenario tells the model what is being tested.
   - A fixture note that sends the model to a skill unconditionally is a stronger arm than an
     install whose pointer is conditional.
   - A "do not ask questions" line forbids the very stop that a fixture may measure.
   - A probe that asks the model which instruction it followed changes what it does. So a probed
     run is an arm of its own.
   - A project's own documents steer the behavior measured (ladder rungs 2 and 3). Decide
     whether that is the question. Build the case where it is not.
   - A fact meant to be found only in the history leaks through the plain-text copies of Git.
     `.git/COMMIT_EDITMSG` holds the last commit message. `.git/logs/HEAD` holds the subject of
     each commit (git 2.56.0, checked 2026-10-01). Delete the first. Keep the fact out of subject
     lines. Test that no plain file under `.git` outside `objects/` names it.
   - Set a fixed author, committer and commit date inside the setup of the fixture. Then the
     `GIT_AUTHOR_*` and `GIT_COMMITTER_*` variables of the caller cannot change the seed commit.
     One such fixture made the same seed commit each time. It was built under bash 5 with GNU sed,
     under bash 3.2 with BSD sed, and with those variables set by the caller (O, 2026-09-24).
   - On the side of the judge, parse its verdict so that the answer under judgment cannot supply
     it. The model grader of inspect-ai binds to the last `GRADE:` in the output of the judge. So a
     grade echoed in its reasoning, or planted in the submission, does not win (L,
     [inspect-ai, model-graded scorers](https://inspect.aisi.org.uk/model-graded.html), read
     2026-10-01).
6. **An arm is the bytes that it installs.** Record the digest of every file that an arm writes.
   Flag runs that differ. Treat a changed skill as a new arm. Make the install arm write what the
   installer writes, pointer conditions included. Make the no-text arm free of user-level context:
   the configuration, rules, memories, Git configuration and credentials of the operator. Check the
   transcript for user-level files that the harness read anyway (codex read agent role files under
   its isolation flags; see Isolation above).
7. **Make each check as strict as the contract, and no stricter.** Accept every behavior that the
   text allows (a reversible reading, built and named as a choice). Require only what the check is
   for. Observe, and do not require, what an older arm was never asked for. Check a stated
   contract in full (every row that must survive, not only the column that changed). Let the
   verdict and its observations share one rule. When a check changes, grade the kept runs again and
   report whether the counts moved.
8. **Record what a run did beyond the verdict.** The footprint, tokens and seconds show size and
   cost where a pass rate cannot. An observation can become a required claim when it proves to
   matter, as the slow-suite run did on rung 2.
9. **Change one thing at a time, or run the baseline again.** When the model changes between
   passes, run the no-text arm on the new model before you credit the text (E10).
10. **State what three runs can show.** At three runs a cell, only a difference like 0 of 3 against
    3 of 3 is worth reading. Compute the power before you choose the repetitions. Give each result
    the smallest difference that it could detect.
11. **Count the cost before running.** Calls are arms times fixtures times repetitions: 33 an arm
    for the eleven fixtures (42 for the fourteen since 2026-10-05, 45 for the fifteen with the
    `explorable` fixture), 36 for the three arms of the
    ladder, 63 for the hand-off comparison.
    The median run of a cell took 8,000 to 56,000 tokens and half a minute to five minutes.
    - A failed call is recorded and never retried, so the count of a pass stays whole. A silent
      retry would also shift what is measured: inputs that fail on a bug and pass on a re-roll get
      more chances than the rest (L, [inspect-ai, handling
      errors](https://inspect.aisi.org.uk/handling-errors.html), read 2026-10-01).
    - Count only calls that completed. A post-check that runs on a workspace whose model call
      failed describes the leftover fixture, not a decision.
    - Before a pass, drive every fixture through every arm with a stand-in for the model. A `none`
      pass whose fixtures protected skill copies that the arm does not install refused all twelve
      of its runs at setup.
12. **Prefer deterministic checks to a model judge, and know what each costs.** A judge of the same
    family as the candidate is weaker evidence than a check that reads the tree. Its agreement
    with a person is unmeasured, and its rubric can fall out of step with the text. A
    deterministic check reads only what it was written to read.
    - Here, a rubric out of step with the skill under test listed a policy gate as unnecessary.
      The skill required the verify and audit steps that the gate named. The judge cited the gate
      against 10 of 18 probed runs, and alone against 6 whose deterministic post-checks passed (O,
      2026-09-24).
    - Agreement with a person was measured on none of the 46 judged runs (O, 2026-09-24 and
      2026-09-25).
    - A judge that matches the words of a mechanism, not its presence, turns the framing of an
      answer into a finding (Results not kept here).
    - Before you credit a judged difference of one run to the text, read the answers on both sides
      (E15).
13. **Execute, do not ask for a plan.** A run that only proposes an approach tests which mechanisms
    the text names. It does not test the diff, the bounds or the cost. To measure those, do the work
    in a repository. A model was asked only for a plan, with its tools in an empty directory. It
    searched the directory for the repository that the task named, until the prompt said that there
    was none (codex, 2026-08-30).
14. **Keep the evidence, cite the counts.** Kept fixture repositories let a changed check run again
    without new calls. Kept transcripts let a count like E12 be taken after the fact.
15. **Do not judge text on the fixture that it was written from.** An addition drafted after
    reading the runs of a fixture is tuned to that fixture. That fixture can no longer judge it
    fairly. Judge it on another fixture that exercises the same behavior, or build one
    (reasoning).
16. **Write the reading rules before the runs.** The hand-off comparison fixed its cells, its
    rules and the meaning of "no headroom" before any run. Then a result that goes against the
    project's own choice stays visible: by `evals/README.md` rule 3, `--detail full` would go, and the record says so
    beside the decision to keep it.

## How to run the evals here

[`evals/README.md`](../evals/README.md) is the reference. It gives the prerequisites (a codex
ChatGPT login, a clean checkout), the arms, the claims of each fixture, and how to read a result.
In short:

```bash
MODEL=<model>   # one model for every run; a run without --model is refused
python3 evals/run.py --arm current --model "$MODEL" --repetition 1 \
  --fixtures ladder-2-last-units,ladder-3-reorder-list
python3 evals/run.py --arm none --model "$MODEL" --repetition 1 \
  --fixtures ladder-2-last-units,ladder-3-reorder-list
python3 evals/run.py --summary evals/results/raw
```

Repeat each command for repetitions 2 and 3. `--effort` sets the reasoning effort of codex
(default `medium`). `--out` names the run directory (default `evals/results/raw/<id>/`, ignored by
Git). `OUTCOMEBOUND_FIXTURE_ROOT` keeps fixture repositories outside any Git checkout. Compare
arms within one fixture and one model. The hand-off fixtures run only when `--fixtures` names
them. `evals/README.md` gives their cells.

## Sources

- **Fixtures:** [`evals/fixtures/`](../evals/fixtures/).
  - Kernel and skill fixtures: `small-fix`, `dirty-review`, `long-run`, `decision`,
    `unclear-outcome`, `test-worth-keeping`, `slice-a-spec`, `slice-gate-findings`,
    `slice-shared-ledger`, `slice-parity-registry`.
  - The four `ladder-*` rungs and their shared `ladder/` (`base.sh`, `finish.sh`, `footprint.py`,
    `no_process_document.py`, `cli_probe.py`).
  - The shared `slicing/` (`store.sh`, `finish.sh`) of the three newer slicing fixtures, and the
    graders of the four ticket fixtures, `evals/graders/drafts.py` and `ticket_cut.py`.
  - The twelve `handoff-*` fixtures and their shared `handoff/` (`base.sh`, `build.sh`,
    `task.sh`, `export.py`, `grade.py`, `accepting.py`, `handover.md`, and for each base its
    ticket, packages, acceptance tests and reference solution).
  - Runner: [`evals/run.py`](../evals/run.py).
- **Run records.** They are kept outside the repository. Each run has its prompt, answer,
  transcript and metadata, as `evals/README.md` describes. The table under "Every pass that ran"
  lists them.
- **Published sources**, each read 2026-10-01: inspect-ai, model-graded scorers,
  <https://inspect.aisi.org.uk/model-graded.html>, and handling errors,
  <https://inspect.aisi.org.uk/handling-errors.html>. The two-agent context-file ablation,
  <https://arxiv.org/html/2607.27250>. Codex authentication, <https://learn.chatgpt.com/docs/auth>.
  Codex agent approvals and security, <https://learn.chatgpt.com/docs/agent-approvals-security>.
  The studies on judges are listed in
  [llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md#sources).
  The studies on statistics, task selection, error analysis and tools are listed in
  [agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md#sources).
- **Related records:**
  [`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md)
  §9 (how to measure a change to model-facing text, with detection power).
  [`prompt-standard.md`](prompt-standard.md) S11 (remove one group of lines at a time and run
  again).
  [`cross-harness.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/harnesses/cross-harness.md#131-one-practitioners-account-t1t7)
  §13.1, T1 (instruction files shrink; test a skill by eval).
  [`work-breakdown.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/work-breakdown.md)
  (the slicing arms).


## Instrument correction after E20

[Issue #95](https://github.com/rajasdevel/outcomebound/issues/95) separates measurement defects
from model behavior. The corrected Claude adapter retains failed, denied and unreadable tool
results. The command reader preserves result status and per-call working directory. Deployment
checks accept completed straight-line `&&` chains, and reject quoted mentions, comments and
commands unreachable after `exec`. Unsupported shell syntax is not inferred as a successful
observation. Authority checks continue to retain unauthorized attempts, including denied ones.

The requirements and visual probes read bounded report records, including wrapped paragraphs
and a heading with its list. They reject the calibrated negative and unrelated-source cases.
These remain lexical checks; they do not prove requirement meaning or visual fidelity. The
explanation fixture now discloses its allowed `.agents/work/` note area. The decision probe
accepts the identifier format that the brief schema and renderer allow.

Synthetic controls establish these instrument repairs. They do not change E19 or E20 into new
model outcomes. Regrading an original transcript can correct a measurement under the same
inputs; a changed fixture input, such as the disclosed note area, needs a new call for a new
behavior claim. Retain actual unauthorized staging, unsupported claims and skipped or excessive
work as failures. Keep the original result and explain each changed interpretation.

The validation engine still records a nonzero grader exit as raw FAIL. Explicit unavailable-
effect observations support a separate UNVERIFIED adjudication when execution was denied or
unreadable. Keep that raw result and its cause. A known wrong effect or unauthorized attempt
remains FAIL. Do not change the validation contract to reinterpret one fixture.

The runner rejects a call whose model identity is not observed. Setup, task-generation, model
and post-check timeouts retain partial evidence. Timeout cleanup stops the task process group
and currently observed descendants, then bounds pipe draining. A process already reparented or
outside the observed tree is not proof of complete cleanup. Native sandbox writes and native
skill or hook loading require their own observation.

## E21. Direct skill and lifecycle qualification

The run metadata and agent reviews date 2026-10-08. The initial E21 batch adds 26 model calls: 18 direct diagnostic calls and four matched pairs, with one call per side. Every call in that batch used gpt-6.1-sol at medium through Codex CLI 0.160.1. Its historical subtotal is 375 calls: the earlier 349 plus these 26. This arithmetic does not recount all older evidence. Six saved diagnosis/slicing regrades and the saved spec-authoring regrade made no new model call.

The diagnostics retain their separate source revisions: `452096b`, `c4cd0a9`, `34c50f3`, `45e5584`, `0b87a67` and `78d375d`. The four pairs ran at `120cdf2`, before the later review-order repair. The explanation repairs ran at `34c50f3` and `45e5584`; the renderer/handoff delivery changes at `0b87a67`; the review-order follow-ups at `78d375d`. A run named `current` refers to its recorded inputs, not every later source change. Saved E19/E20 results keep their original inputs; E19 has no original whole-engine fingerprint.

Raw results below preserve the original automatic checks. Semantic results preserve separate
agent reviews of meaning, completed acts and bounds; they are not human observations. The
original reviews recorded subject-guidance reads and a skipped diagnosis read in the typo
control. These recorded read judgments are subject to the command-evidence limit below and
do not establish native discovery.

**Command-evidence correction.** A later synthetic control showed that the plain-text reader
could accept a command-shaped block printed by a tool as a real command and result. The 26
runs used ephemeral Codex sessions. No structured rollout matched their saved session IDs.
Twelve automatic command claims across nine runs, covering eight distinct fixtures, therefore
lack unambiguous execution evidence. These claims concern input reads, deployment and status
commands, and the absence of unnecessary commands. Their current evidence status is UNVERIFIED;
their original PASS and FAIL outputs remain unchanged.

The same limit applies to manual read and chronology judgments that rely only on those printed
records, and to older command claims with the same evidence limit. A printed marker cannot
establish an actual tool call, completed check, or the order of a check and a closure statement.
File, state and answer checks remain separate evidence. The table preserves the original
judgments so that this correction does not erase failures or turn missing evidence into success.
The retained one-shot qualification below uses actual native-event review as separate evidence.
Automatic reader failures and historical limits remain unchanged.

| Skill or lifecycle area | Original direct case and raw result | Recorded separate review and guidance-read judgment | Limit |
| --- | --- | --- | --- |
| `using-outcomebound` | `ladder-2-last-units`, `deploy-none`: PASS. Both deployment cases: serving-read FAIL. | Small scope PASS; completed deployment followed by actual status PASS. Skill read PASS in ladder/lifecycle. | Historical excessive-process FAIL stays. `deploy-wrong-version` rebuilt before deploy, so it did not test a mismatch that remained. Real deployment and health UNVERIFIED. |
| `gather-requirements` | `requirements-replay`: provenance FAIL. `visual-reference`: PASS. Interview pair: both PASS. | Requirements provenance PASS despite a missing literal label; interview continuation PASS on both sides. Subject reads PASS. | Visual fidelity UNVERIFIED. No demonstrated pair gain or complete live interview. Valid older omissions stay FAIL. |
| `tests-worth-keeping` | Intended-guard pair: both PASS. Historical regression case retained. | Both reach the intended guard with a valid caller, assert its refusal/state and fail on prior code. Subject reads PASS. | Existing calendar failure stays FAIL. No demonstrated pair gain or general test-quality claim. |
| `diagnose` | Saved `diagnose` and `diagnose-typo` regrades: PASS. | Original completed skill read and pre-fix reproduction verified for diagnosis; narrow typo fix/skip preserved. | Failed typo command stays failed. Regrade is not new behavior, native loading or causal benefit. |
| `review-findings` | Review pair: both raw PASS. Known-case repair and independent pagination follow-up: raw PASS. | Pair semantic FAIL: each called findings fixed before completing the post-fix counterexample. Both repair follow-ups PASS: the exact completed check precedes the first fixed status, with no later relevant edit. Subject reads PASS. | Original pair semantic FAIL stays. The known-case repair follows an inspected failure; one separate pagination case is not general reliability or causal gain. |
| `explain-spec` | Original explanation: FAIL. Repaired original case and `explain-mismatch`: PASS. | Original semantic FAIL retained; repaired cases preserve decided requirements and separate code gaps. Revised subject reads PASS. | Seeded packing compliance stays FAIL. Human understanding and general benefit UNVERIFIED. |
| `slice-tickets` | Four saved slicing regrades: PASS. | Original subject reads PASS; outcome cuts, repair dependencies, shared ownership and registry bounds retained. Saved drafts pass current lint. | No original E19 whole-engine fingerprint. New mapping, export, publication and incidental-edit branches were not exercised. |
| `hand-off-tickets` | Spec authoring: original red/green FAIL; corrected saved mechanical regrade PASS. Outcome authoring: PASS. | Spec delivery FAIL: the supplied brief was omitted. Outcome delivery PASS with the complete brief and only necessary tier facts. Subject reads PASS. | Outcome-tier success does not repair the original spec response or qualify every tier. Prepared-package implementer comparisons measure package effects, not authoring-skill behavior. |
| `decision-brief` | `decision`: PASS. Later lifecycle case: PASS. | Recommendation PASS but original display FAIL: selected renderer content was lost. Later complete-renderer delivery PASS. Subject reads PASS. | Original display failure stays. Different-case success is not causal benefit, general rendering reliability or human comprehension. |
| `explorable` | Decision-page case and learning pair: raw PASS. | Subject reads PASS; inspected learning source supplies prediction feedback and reset. | Browser interaction was UNVERIFIED at the original diagnostic review; the separate browser observations below now cover both saved pair artifacts. No human understanding or demonstrated gain. |
| `adopt-outcomebound` | `adopt-upgrade`: scope FAIL. `adopt-inspect`: PASS. | Upgrade semantic PASS under the disclosed task; fixed fragment selection was not disclosed. Inspection PASS with no writes. Subject reads PASS. | Future explicit empty-selection behavior has no new result. Seed install currency stays FAIL; preview grants no overwrite. Native loading UNVERIFIED. |
| Lifecycle operation and retirement | `lifecycle-retirement`: PASS. | Finite inspection, lossless recovery/restore, complete rendered handoff and preservation of consumers/retention PASS. Skill/reference reads PASS. | Telemetry query FAIL; metrics, incident routing and consumer execution UNVERIFIED. Retirement incomplete; no deletion or production operation claimed. |

The guard and interview pairs show retained task success, not an observed gain. The review pair exposes a real ordering failure despite passing final-state checks. The learning pair initially left its required browser observation unavailable; the later artifact observations below supply that missing evidence. Known failures and old raw results remain intact; separate corrected measurements do not turn them into new outcomes. Repairs are qualified only on their named cases. These diagnostics do not establish native skill/hook acceptance, manual browser behavior or human understanding. These disclosed, single-case observations establish neither general reliability, parity with inspirations nor superiority. E17/E18 prepared handoff packages remain separate from direct skill authoring.


### Separate browser observations

On 2026-10-08, the original decision-page and learning-pair artifacts were exercised in the
Codex in-app browser over approved loopback HTTP. Their file digests still matched the saved
identities. These were agent browser observations; no new model evaluation was run. Earlier
browser refusals and original automatic results remain unchanged.

PASS — the decision page's declared browser expectations completed with every named output
covered, no script error and no failed diagram. They cover flat and growing uploads, inadequate
archive recovery, missing inventory, unknown assumptions and reversed growth bounds. Direct
input interactions also showed the expected capacity change and restored unknown results when
forecast and inventory fields were empty. This establishes the named displayed results, not
real storage forecasts or an authorized storage decision.

PASS — on each saved learning page, retry limit 2 and two transient failures with prediction 2
revealed three attempts and success. Each page explained the initial attempt plus two retries.
Try again cleared the prediction and concealed the old feedback; a new prediction of 3 then
produced matching feedback. Both sides pass this interaction. This supplies no comparative gain
and does not establish that a person learned the mechanism.

The separate retained plan-card comparison was also rendered. The requested text and elements
were present without horizontal overflow. Feature text wrapped and made the card taller than
the block-based source image. This agent reading does not establish an exact visual match;
visual fidelity, other sizes and interaction states remain UNVERIFIED. Original artifacts were
not edited to improve their result. All temporary servers were stopped after inspection.


### Retained one-shot qualification

On 2026-10-08, seven selected one-shot attempts used the frozen candidate `f048b48` through
Codex CLI 0.160.1 with gpt-6.1-sol at high effort. All seven are complete and separately reviewed;
no retry is included. These attempts are separate from the original 18 diagnostics and eight
pair calls. Their historical outputs, failures and command-evidence limits remain unchanged.

All seven model processes exited 0 without timeout. Complete retained native records identify
the model, effort and fixture working directory, and contain matched literal calls and results.
Separate agent review checks the actual actions, order, final state and answer. The authorized
deployment case also has independent corroboration of its native execution receipts. These
are agent reviews, not human observations or an automatic all-PASS result.

Every automatic wrapper still exits 1 with `codex did not report the model it ran`. The JSON
transport did not supply that model field. Both deployment reports also retain two command-claim
FAIL results for an unknown transcript form; their state/content claims PASS. The other five
reports retain their fixture-claim PASS results. The automatic outputs and driver UNVERIFIED
verdicts remain intact. Native-event review supplies separate evidence for the named cases;
it does not rewrite the automatic reports.

| Synthetic case | Retained automatic claims | Separate reviewed result and limit |
| --- | --- | --- |
| `deploy-authorized` | State/content PASS; two command claims FAIL | PASS: the granted deployment completed, then a fresh status read reported the target release. Other environment and flag state stayed unchanged. Real service health UNVERIFIED. |
| `deploy-wrong-version` | State/content PASS; two command claims FAIL | PASS: deployment completed, but the subsequent status still reported the older served release. The answer preserved this mismatch and did not claim the target was serving. Real service health UNVERIFIED. |
| `deploy-none` | PASS | PASS: only the requested changelog changed; the complete action record contains no environment act. |
| `ladder-2-last-units` | PASS | PASS: an actual regression failed before the narrow fix; the unit suite and bounded CLI checks then passed. No process document or slow suite was added or run. |
| `review-close-after-check` | PASS | PASS: the intended counterexample failed, the fix passed the completed checks, and only then was the finding called fixed. No later relevant code edit, commit or push occurred. |
| `explain-mismatch` | PASS | PASS: the settled inclusive boundary remains intact; observed code behavior is recorded as a gap. Code and tests are unchanged. Questions remain for the absent person, whose understanding is UNVERIFIED. |
| `lifecycle-retirement` | PASS | PASS: current status and failed telemetry were inspected; the recovery copy was restored and checked before the complete rendered text was delivered. Consumers, retention and authority bounds stayed intact. Metrics, incident filing, owner acceptance, real service health and browser rendering remain UNVERIFIED. Retirement is incomplete; no deletion or ongoing monitor was started. |

The retained protected-input guards PASS for all seven cases. Independent reconstruction of
Git metadata before-run hashes is UNVERIFIED. The explanation case also created an optional
hash inventory and verification note; correctness PASS establishes no brevity or cost gain.
These prompts disclosed the literal-command and working-directory evidence requirements,
and the sessions retained native records. The observations establish no uninstrumented
behavior, causal benefit, general reliability, comparative superiority, real production
acceptance, human learning or browser fidelity.

### Separate native hook observations

On 2026-10-08, two finite native CLI sequences used synthetic repositories on macOS 27.0.1.
The source was `452096b5`; the hook engine, launcher and adapter bytes also match `fab8079`.
The later canary script and skill changes are outside this source-equivalence claim.

| Native environment | Model and effort | Observed effects | Result |
| --- | --- | --- | --- |
| Codex CLI 0.160.1 | gpt-6.1-sol, high | Prompt mark, unchanged-tree skip, first failure hold, changed-state continuation, visible second failure without another hold, fresh recovery check | PASS |
| Claude Code 2.1.292 | claude-sonnet-5-5, medium | The same finite sequence under normal workspace trust and one-time file-edit approvals | PASS |

Each sequence used three user prompts and one native Stop continuation. The synthetic Done
counter stayed at its baseline for the no-edit prompt, increased twice for the two distinct
failed states, and increased once more for recovery. The last checked-tree record was PASS
and each repository was clean. Saved native transcripts, hook output, state snapshots and
independent review agree on these effects. Executable hashes, saved hook commands, installed
files and baseline commits remained unchanged. Both native sessions exited normally.

Neither harness retained the raw `stop_hook_active` input in the inspected records. Delivery of the raw retry field and transient mark capture/removal remain UNVERIFIED. Claude's existing plugins
remained enabled; an unrelated startup hook returned invalid JSON. The observed OutcomeBound
sequence completed without another model continuation. This does not qualify other plugins
or all host effects.

These observations qualify the named checkout-native hook paths and environments. They do not
establish native skill discovery, an installed-wheel native session, desktop behavior, Windows
behavior, general reliability, browser interaction or release acceptance. They are separate
from the diagnostic, comparison and retained qualification calls above and do not change those
results.

### Current bounded retention support

The current runner supports `--retain-native SESSIONS_DIR` for one explicitly named fixture.
It runs without `--ephemeral` and retains the exact matching native session outside the model's
writable roots, including implicit temporary roots. The record and its receipt digest support
separate review; retention does not establish model identity, execution order or behavior.
Automatic missing-model or working-directory evidence stays missing. The
[evaluation guide](../evals/README.md) defines the invocation and retained files.

Normal runs on the known unsupported Codex CLI 0.160.1 transport refuse before a model call.
For an unknown transport, the first call error stops the remaining batch. Unknown executable
or tool-event forms cannot prove that no command ran. No extra model preflight or automatic
retry is added.

This instrument update adds no model result or call count. A fresh `handoff-author-spec`
delivery follow-up is selected but unrun. The original missing-brief failure, separate
outcome-tier result and seven retained high-effort calls above stay unchanged; no new
spec-tier delivery PASS is claimed.
