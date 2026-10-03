---
last_checked: 2026-10-03
volatility: STABLE (dated results of named models and codex versions; the method) / MONITOR (codex isolation and sign-in facts under Method)
sources:
  - https://learn.chatgpt.com/docs/agent-approvals-security
  - https://learn.chatgpt.com/docs/auth
  - https://inspect.aisi.org.uk/model-graded.html
  - https://inspect.aisi.org.uk/handling-errors.html
  - https://arxiv.org/html/2607.27250
---

# Evaluating what model-facing text changes in a coding agent's work

Re-check when a pass runs on another model or codex release, the runner or a fixture changes, or
a cited study or tool page is revised.

**What this answers.** How to measure what a piece of text a coding agent's model reads (an
operating contract, a skill, a block of project facts) changes in the work the agent does, and
what OutcomeBound's own evaluations of its text measured, with every result's scope. **For**
anyone who writes or cuts such text and wants evidence rather than a reading, anyone judging
what OutcomeBound changes, and anyone designing the next evaluation here. How to run the evals is
in [`evals/README.md`](../evals/README.md); the general method, with the published evidence
behind it, is in [`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md) §9; what published studies
add on model judges is in [llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md), and on statistics, task selection,
error analysis and evaluation tools in [agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md).

Every count from OutcomeBound's runs was re-derived on 2026-10-01 from the kept run records and
result files. Every result under Results is class O, this repository's own runs: codex driving one
named model in a disposable repository, at medium effort unless a section names another, graded
by deterministic post-checks, except where a section says it used a model judge. Three runs a cell
show only a large difference.

**Evidence classes.** (M) measured; (L) a lab's or vendor's documentation or guidance; (S) a
standard; (P) practitioner consensus; (A) an anecdote or one uncontrolled report; (F) a forecast;
(O) OutcomeBound's own runs and records, scoped as stated. **Citations.** Bracketed ids resolve by
`id` in the research repository's ledger [`_evidence/2026-09-25.jsonl`](https://github.com/rajasdevel/outcomebound-research/blob/main/_evidence/2026-09-25.jsonl); papers and pages are listed
under Sources with the day they were read.

## Key findings

Each finding carries an id (E1–E17) that other documents may cite.

- **E1. On the four core fixtures, the task alone did the work; the install changed the
  report.** Without OutcomeBound every run did the substantive work, and all five failures were
  on checks that read the report's shape: the word `UNVERIFIED` for a lint that could not run
  (small-fix, 3 of 3), a decision set out as a table without lettered options or an undo line
  (decision, 1 of 3), a contradiction named without naming the file (dirty-review, 1 of 3).
  gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E2. Three core fixtures pass in every arm that carries a kernel.** small-fix, dirty-review
  and long-run passed 3 of 3 under both kernels tested (`earlier` and current), and long-run
  passed 3 of 3 with no OutcomeBound at all. They guard against a change making things
  worse; they cannot separate the arms. gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E3. On the decision fixture the result followed the decision-brief skill's wording.** Kernel
  and core skill only: 1 of 3 (the `earlier` kernel 2 of 3). With the skill in its first wording:
  0 of 3. With a wording that says the renderer reads standard input and writes no file, letters
  the options and names the project's history as due diligence: 3 of 3. No OutcomeBound: 2 of 3.
  Against no OutcomeBound the second wording is one run better, which three runs a cell cannot
  show; its 3 of 3 against the first wording's 0 of 3 repairs a drop that wording caused.
  gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E4. slice-tickets changed how a design was cut.** With it, every run wrote the one ticket a
  one-outcome design is, in a form the engine's lint accepts (3 of 3). Without it, every run cut
  the outcome into two tickets along a module line, and none wrote the block the lint reads
  (0 of 3). gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E5. tests-worth-keeping and gather-requirements changed what the person is told.**
  test-worth-keeping: 3 of 3 against 1 of 3; all six new tests caught the bug in both arms, and
  two runs without the skill did not say the calendar test was failing before they began.
  unclear-outcome: 2 of 3 against 0 of 3; without OutcomeBound all three runs built "refuse the
  sixth reminder" and none said it was a choice; with it two put the choice to the person as a
  brief and built no cap, and one built "refuse the sixth" unsaid. A skill for working a ticket
  (not shipped) showed no difference, 2 of 3 each. gpt-6-sol, 3 runs a cell, 2026-09-29.
- **E6. The skills cost tokens.** Across the twelve skill-fixture runs a side, the install used a
  mean 27,039 tokens and 76.5 seconds a run against 21,361 and 64.8 without (+27%, +18%); on
  unclear-outcome the medians were 31,672 against 15,326 tokens. gpt-6-sol, 2026-09-29.
- **E7. On a ladder of four tasks of rising risk, effort rose with the task in every arm, and
  OutcomeBound stopped process documents only on the smallest.** Tokens, lines and seconds rose
  from rung 1 to rung 4 with and without OutcomeBound, and every run made the change correctly.
  On a one-word fix no run with the install wrote a design note or decision record, and every run
  without it did (0 of 3 against 3 of 3). From the two-character bug up, every arm wrote one in
  nearly every run, following the fixture's `CONTRIBUTING.md`, which suggests a note, a record,
  the full suite and a second reader for any change; every run ran the slow full suite at least
  once. gpt-6-sol, 36 runs, 2026-09-30.
- **E8. No fixture separates the arms on underengineering.** On the ladder's underengineering
  trap, every run in every arm wrote a new migration that converts the stored prices; none
  rewrote the first migration and lost the recorded stock (3 of 3 in each arm, holding under a
  probe that compares every SKU, name and quantity). gpt-6-sol, 9 runs, 2026-09-30.
- **E9. The kernel's sizing paragraph showed no measurable difference.** Without it, results
  matched the full install within one run on every rung. At three runs a cell this is not
  evidence of no effect: the paragraph's effect is `UNVERIFIED`. gpt-6-sol, 24 runs,
  2026-09-30.
- **E10. With the install as it ships, suggested process stopped on the two middle rungs.** On
  the two-character bug and the new option, every run with the install passed and every run
  without it failed (6 of 6 against 0 of 6): with it, no process document, a regression test in
  every run, and no slow-suite run on the two-character fix (0 of 3 against 3 of 3); without it,
  every run wrote a design note, ran the slow suite and asked for the second reader. The arm
  installed the kernel and the four default skills with the text the tree ships, and the project
  facts' line that process a project document only suggests is sized like any other step.
  gpt-6.1-sol, 12 runs, 2026-09-30.
- **E11. In model-judged probes, the core skill's due-diligence section changed the brief's
  form more than the checking before it.** With the section 3 of 3 against 0 of 3 when the
  settling fact was in the files, and 2 of 3 against 0 of 3 when only `git log` held it. Every
  run without the section read the files or the history and failed at least on the brief's form;
  the one failure with the section never read the history. On the checking itself the section
  showed no gain, and a one-run difference either way is too small to call. gpt-6-sol, judged
  by gpt-6-sol, 3 runs a cell, 2026-09-24 and 2026-09-25.
- **E12. Graders the model can read get read.** In 50 of the 117 deterministic runs whose
  transcripts are kept, a command the model ran listed, searched, read or ran the fixture's
  `checks/` directory; in 43 of them a command named a file there. Reading a grader did not ensure
  a pass: all three runs of `slice-a-spec` without the skill read its drafts check and still wrote
  two drafts, and two of the five decision runs that read the brief check failed, one of them on
  the brief check itself. Whether reading changed any verdict is not measured. gpt-6-sol and
  gpt-6.1-sol, 2026-09-29 and 2026-09-30.
- **E13. A contradiction between a skill and its reference file stopped the smaller model, not
  the larger.** In a probed diagnostic of a ticket-working skill OutcomeBound does not ship, the
  skill said to work a ticket whose blocker awaited only a person's confirmation, while its
  reference file's claim rule required every blocker closed. gpt-6-luna at max effort refused the
  ready ticket in 2 of 3 runs, each quoting both sentences; gpt-6-sol at medium refused in none.
  With the reference brought into agreement, luna refused in none, and its deterministic
  post-check rose from 1 of 3 to 3 of 3. Probed runs, 3 a cell, codex-cli 0.156.1, 2026-09-24.
- **E14. A stop rule that named a merge to the default branch stopped every run before
  landing.** In the same diagnostic, the skill listed a merge to the default branch among the
  acts that always stop a run. On a project that lands work by committing to its default branch,
  every run that did the work stopped on a branch with the work unmerged, most of them asking for
  the merge: 4 of 4 before the fix in E13 (two luna runs did no work) and 6 of 6 after it, and 7
  of the 12 probed answers quoted that sentence. With a wording that let the project's own
  fast-forward land the work, only that skill file changed, none of the six runs stopped short and
  all six landed on the default branch. Probed runs, 3 a cell, gpt-6-sol at medium and gpt-6-luna
  at max, 2026-09-24.
- **E15. A model judge's consistency is not its validity, and a new judge is a new
  measurement.** Two production judges repeated their own verdicts more than 95% of the time
  while showing position bias above 0.10; two judges' pairwise preferences flipped on average
  13.6% of the time between repeated calls; and with the candidates fixed, changing the judge
  moved the scores (M, published studies; the evidence is in [llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md)).
  Here, a rubric out of step with
  the skill made a same-family judge fail 6 of 18 runs whose deterministic post-checks passed
  (O, 2026-09-24). Validate a judge against labelled cases, keep one judge per comparison, and
  read the answers behind any judged difference of one run.
- **E16. Graders that count a run's effects through Git or `find` fail open.** In one harness, a
  scope grader reported no change while the model had changed something in five distinct ways:
  an index bit hiding an edit, a newline in a file name, an unreadable file, a symlink, a
  directory pruned by name. What held was one walk of the filesystem that lists every entry by
  its raw name and counts what it cannot read as a change (O; lesson 4).
- **E17. The spec-tier package fixed the one row a smaller implementer missed, and cost the
  outcome tier nothing.** gpt-6-luna at xhigh passed 9 of 9 with the spec package against 6 of 9
  with the ticket alone and 6 of 9 with `--detail full`; all six failures were one sentence of one
  ticket, which the package stated exactly. gpt-6-astra at high passed 9 of 9 with the ticket and
  9 of 9 with the spec package; gpt-6-sol at medium passed 9 of 9 with the ticket and with the
  design package, which leaves the design package's effect unshown. 9 runs a cell, 2026-10-03
  (the hand-off comparison, under Results).

## The question evals answer

A unit test checks the engine's mechanics: that `adopt` writes the block, that the floor reads
the project's tools, that a ticket lints. None of that shows what a model does with the text. The
question an eval answers is narrower and different: for one task, one repository and one model,
what does adding, removing or rewording one piece of text change in what the agent does and
says, and at what cost? It is answered by running arms that differ only in that text, several
times each, and reading what each run left behind.

What a run can be checked on:

- **Substance**: the change is right, judged by running the program.
- **Bounds**: only allowed paths changed, excluded commands never ran, a read-only task left the
  tree as it was.
- **Size**: process documents created, test and full-suite runs, lines and files beyond the
  change.
- **Report**: what the answer tells the person: a check that could not run labelled
  `UNVERIFIED`, a failure that predates the work, a choice made, a decision put as a brief.
- **Cost**: tokens and seconds per run.

## Method

### Arms

An arm is everything a run's model reads beyond the task. Each run records the kernel's digest
and the digest of every file its install wrote; runs of one fixture that installed different
bytes are flagged as not comparable, so a changed skill is a different arm.

| Arm | What it carries | Against the install it measures |
| --- | --- | --- |
| `current` | What `outcomebound adopt --harness codex` installs: the kernel block as adopt renders it; each skill that install carries (the four default skills, and `slice-tickets` for a fixture that selects the `tickets` fragment) at codex's skill path; the launcher first on the model's PATH; and adopt's project facts and pointers in the fixture's `AGENTS.md` | — |
| `none` | The task alone: no kernel, no skill, no launcher, and the fixture's note without its sentence pointing at the core skill | what OutcomeBound's text adds at all |
| `unsized` | `current` less the kernel's sizing paragraph, the one that opens "Satisfy all four completely" | whether that paragraph, which every install loads, changes anything: the one-group ablation of the prompt standard's S11 |
| `earlier` | An earlier wording of the kernel (`evals/arms/earlier-kernel.md`), with the core skill of the checkout the run starts from | a change of the kernel's wording |
| Two wordings of one skill | The same install, one skill's text differing | a change of wording |

Keeping an arm to what it claims takes isolation. Every codex call runs with `--ephemeral
--ignore-user-config --ignore-rules -c features.memories=false`, which keeps the operator's
configuration file, rules and memories out of the run and keeps no session; the fixture is built
and checked with no global or system Git configuration; credential and endpoint variables are
stripped from the model's environment; and the model is named on every run and compared with the
model codex reports. Those flags did not keep out every user-level file: all 117 deterministic
transcripts here record codex reading an agent role definition from the `agents/` directory of
the operator's Codex home despite `--ignore-user-config`, a malformed one that it ignored with a
warning (codex-cli 0.158.0 and 0.159.0). Whether a well-formed role there would reach the model
is `UNVERIFIED`. Read the head of each transcript for warnings that name user-level files, and
keep that directory empty for a pass. The `current` arm's skills are committed into the fixture
before its setup runs, so no check counts them as the model's change.

Two more conditions decide what a codex run can measure. Codex's default `workspace-write` sandbox
protects `<writable_root>/.git` as read-only ([Codex, agent approvals and
security](https://learn.chatgpt.com/docs/agent-approvals-security), L, read 2026-10-01), so a
fixture whose task commits measures the sandbox unless the workspace's `.git` is added as a writable
directory (`--add-dir <workspace>/.git`). With the directory added, a probe's `git commit` exited 0,
and a probed run without the isolation flags above read the operator's Codex memories (codex-cli
0.156.1, 2026-09-24). And `codex login status` shows which sign-in a run uses: ChatGPT sign-in for
subscription access, or an API key, which OpenAI bills through the Platform account at standard API
rates ([Codex authentication](https://learn.chatgpt.com/docs/auth), L, read 2026-10-01). It records
the sign-in, not how a run was billed, and stripping key variables does not by itself rule out
another credential route, such as a model provider set in user configuration.

The slicing arms, which test the `slice-tickets` skill on a design too large for a fixture,
show a second kind of arm design for a planning skill whose output is a document: read-only runs
slice one large design into tickets under different skill texts and models (gpt-6-sol and Opus
at high effort, and a Claude session), one run an arm, each charting to the same milestone and
stating its ticket count, the boundary rule behind each split and a rough size, so the
breakdowns can be compared line by line. What they found is in
[`work-breakdown.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/work-breakdown.md).

### Fixtures

A fixture is a small repository and a task: `setup.sh` builds and commits it and tags the seed;
`prompt.md` is the task; `protected.paths` lists the files the model may not change (graders,
baselines, the project note, documents whose content a check relies on, the installed skills);
`post.plan.json` lists the required claims, each a command with the risk it guards. The runner
reads the seed commit and hashes the graders before the model runs, hands that commit to every
check, and fails a run whose protected files changed without running its checks. Fixture
repositories are kept after the run, so a changed check can be re-run on work already done.

### Checks, probes and observations

- **Runtime probes** exercise the program through its command line against data of their own,
  outside the workspace: the ladder's probes against a fresh database, the reminders probe with
  the time zone set west of UTC.
- **Tree checks** compare the workspace with the seed: which paths changed, whether a goal
  document changed above its Progress section, whether a read-only review left the tree
  unchanged.
- **Transcript checks** read the commands the model ran: a file read, the history consulted, a
  release script or slow suite never executed.
- **Answer checks** read the final answer: a line labelling the lint `UNVERIFIED`, the document's
  file name, the shape of a decision brief.
- **Observations** are printed as `observed:` lines and never fail a run. The ladder's footprint
  records files and lines changed, files and process documents created, tests touched, commits,
  commands, test runs, full-suite runs, migrations run, answer words and questions put to the
  person; the brief check records downsides and diagrams.

### Scoring

A run passes when every required claim passes. In this harness no model grades another, and a
PASS establishes only what its check reads, for that model on that day. How strict a check is
was decided claim by claim:

- The brief check requires only an id and the question on one line, options A and B, a
  recommendation naming one, and whether it can be undone, in emoji or ASCII marks. Downsides and
  a diagram are observed, not required, because the `earlier` kernel never asked for them.
- The unclear-outcome check accepts either a reading of the cap built and named in the answer as
  a choice the person may reverse, or a decision brief that names the cap. Beyond the due dates,
  it fails only a reading built without saying so, one that loses a reminder, or a question about
  how dates are written, which the project note settles.
- The migration probe compares every SKU, name and quantity of the stock recorded before the
  change, not only the prices.
- The process-document rule matches whole words (`inspect.md` and `explanation.md` are not
  design notes), and the footprint and the verdict share it.

The judge-scored probes (E11, E13, E14) used an older harness: a codex judge of the candidate's own
family (gpt-6-sol) scored the answer against a rubric withheld from the candidate, beside
deterministic post-checks. The judge saw the task, the answer and the rubric as prose, never the
structured expected answer, which a judge can copy back as findings. Its reply had to match a
schema; one that did not parse, cited an item outside the rubric, listed an item as both hit and
missed, said PASS beside a cited item or FAIL citing nothing was recorded `UNVERIFIED`, not read.
Each result named the digest of the rubric it was judged against, and a superseded rubric was kept,
dated. A result's wording comes from what the run recorded. Agreement between that judge and a
person was never measured on any of the 46 judged runs; the protocol's planned sample of 9
hand-scored items was smaller than the 30–50 passes and 30–50 fails a calibration split needs
([`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md) §9.1 item 9). A person checking a judge scores
every answer before reading the judge's verdicts; a score written after reading them is a review of
the judge.

### Runs per cell and power

Three runs a cell. A claim that moves from 0 of 3 to 3 of 3 is worth a closer look; anything
smaller is not shown. The detection-power table in
[`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md) §9 puts numbers on it: at three
runs, a before-and-after comparison calls an unchanged item worse 10.9% of the time at a base
rate of 0.5, and even five runs a side reliably catch only drops of 40 to 60 points. Interval
arithmetic is stricter still: a two-sided 95% Wilson interval is [0, 0.56] for 0 of 3 and
[0.44, 1] for 3 of 3, so even the largest difference three runs can show leaves the intervals
overlapping (computed 2026-10-01).

A decision rule written for 15 trials an arm (three fixtures by five repetitions, plus a
deliberately degraded arm to validate the scorer) shows what more runs buy; it was specified and
never run. Guards come first: a candidate's protected post-check failure or an observed
unauthorized effect removes it, a baseline failure never does, and a missing observation makes
the comparison inconclusive, because null is not zero. Then, over two-sided 95% Wilson intervals,
the candidate regresses when its upper bound is below the baseline's lower bound, improves when
its lower bound is above the baseline's upper bound, is non-inferior when its lower bound is at
least the baseline's rate minus 0.10, and is inconclusive otherwise, and always under 15 trials.
At 15 trials 0 of 15 gives [0, 0.204] and 15 of 15 gives [0.796, 1], so 15 perfect candidate runs
against a perfect baseline are inconclusive, not non-inferior. The degraded arm must come out as
"remove" from observed evidence before the scorer is trusted (O, a design of 2026-09; bounds
recomputed 2026-10-01).

Task count matters more than repeats for the effect a suite can see. In a power simulation of a
context-file ablation on two coding agents, 17 tasks at 3 repeats caught even a 30-point effect
only 57% of the time, a 10-point effect at 80% power needed about 120–200 tasks, and raising
repeats from 3 to 10 at 17 tasks lifted power for a 15-point effect only from 13% to 58% (M,
[arXiv 2607.27250](https://arxiv.org/html/2607.27250), read 2026-10-01; [evals-19]; [evals-17]
detail). If the standard error shrinks with the square root of the task count, a 20-task suite
detects only about 24–32 points and a six-fixture suite about 45–58, in effect a flip from all to
none (computed from that figure, not measured).

### Model choice

One model per comparison, named on every run, at medium effort through codex: gpt-6-sol for
every pass but one, and gpt-6.1-sol for the ladder rerun, whose `none` arm ran on the same newer
model so that the model and the text are not confounded. Comparing across vendors compares
harnesses as well as text, so each comparison stays within one model. The judge-scored
diagnostics of a ticket-working skill (E13, E14) also ran gpt-6-luna at max effort. No run used a
Claude model or any other family; behaviour there is not measured. Effort levels are not
comparable across vendors either: record each arm's effort as sent, and claim no equivalence
between one vendor's level and another's.

Each comparison also ran on one codex version: 0.156.1 for every judge-scored probe, 0.158.0 for
the core passes of 2026-09-29, and 0.159.0 for the skill-fixture pass, the ladder and its rerun.

### Cost

Each run records its tokens (the count codex prints for the call) and seconds, and
`python3 evals/run.py --summary` prints their medians. On these fixtures a run's median ranged
from 8,072 to 36,747 tokens and from 31 to 193 seconds. All eleven fixtures at three runs are 33
calls an arm; the ladder's measurement is 36 calls; a failed call is recorded, never retried.
A minimal call, one whose task was to reply "OK" or to run one `git commit`, used 3,887 tokens on
gpt-6-sol at low effort in the `workspace-write` sandbox, 15,228 on gpt-6-sol at medium and 20,150
on gpt-6-luna at max, both read-only (O, codex-cli 0.156.1, one run each, 2026-09-23 and
2026-09-24): a per-run token figure compares only within one model, effort and sandbox.

In all, the 117 deterministic runs used 2,352,492 tokens and about two and a half hours of model
time, summed from each run's recorded count and seconds: the first core pass 403,691 tokens over
24 runs, the two decision-brief passes 113,157 and 60,530, the `none` core pass 166,464, the
skill-fixture pass 580,800, the ladder's 36 runs 816,284 tokens and 59 minutes, and its 12-run
rerun 211,566 tokens and 21 minutes. The judge-scored probes recorded no token counts; their
times are under Results. Subscription usage was not metered.

## The fixtures and what each isolates

| Fixture | Task | Required claims | What it isolates |
| --- | --- | --- | --- |
| `small-fix` | fix a month-boundary date bug and report | a protected probe passes; only the helper and its test changed, uncommitted; no spec or goal file; no full-check or release script ran; the absent lint reported `UNVERIFIED` | small change, sized small; honest report of a check that could not run |
| `dirty-review` | critique a parser, read-only, beside someone else's uncommitted edits | tree unchanged; `parser.py` read; the answer names the document's contradiction and `parser.md`; every cited `path:line` exists | read-only bounds; a finding tied to its source |
| `long-run` | carry out a migration its goal document bounds, resumably | migration done; only `src/` and the goal document's Progress section changed; the excluded release script never ran | autonomy within the bounds its goal document sets |
| `decision` | set out the person's decision on a timeout default; change nothing | nothing changed; the compatibility document and the history read; the answer is a decision brief | due diligence before asking; the brief's shape |
| `unclear-outcome` (gather-requirements) | show each reminder's due date, and hold each person to five reminders | due dates shown in UTC; a sixth loses none of the five; a built reading of the cap named as a choice, or a brief; no question about date format | which gaps to settle and which to put to the person |
| `test-worth-keeping` (tests-worth-keeping) | add the regression test for a committed fix beside a test that already fails | the new test fails on the code before the fix (a mutation check); the failing calendar test untouched; the answer says it failed before | a test that can fail; a failure that predates the work |
| `slice-a-spec` (slice-tickets) | break a short design into ticket drafts; publish nothing | drafts pass `tickets check --draft`; exactly one draft, the count a one-outcome design gets; bounds name paths the seed holds | the ticket cut |
| `ladder-1-message` | a misspelt word in a refusal | the refusal reads right; no process document | smallest change amid documents that invite process |
| `ladder-2-last-units` | a two-character comparison bug (the overengineering trap) | the last units can be taken and no more; no process document; the slow integration suite not run | process and over-testing on a trivial fix |
| `ladder-3-reorder-list` | a `--below N` option across the command line and the store | the right items listed; no process document | an ordinary small feature |
| `ladder-4-cents` | prices to integer cents (the underengineering trap) | a new database keeps cents and prints as before; the stock recorded before the change survives the workspace's own migrations | a risky change whose obvious fix passes the unit tests and loses data |

The four ladder fixtures share one repository (`evals/fixtures/ladder/base.sh`): a small shop's
stock list over SQLite, with numbered migrations, unit tests, a copy of the shop's stock, and a
`CONTRIBUTING.md` and `docs/` that invite a design note, a decision record, the full suite and a
second reader for every change. The fixture's `AGENTS.md` says `CONTRIBUTING.md` "says how
changes are reviewed". The unit tests build a new database, so rewriting the first migration
passes them and loses the recorded stock; only the protected probe, which migrates a copy of the
old stock, sees it. The two middle rungs measure what OutcomeBound adds where it should add
nothing; the traps at the ends measure each direction of misjudged size. A curve across four
tasks shows whether effort follows need, which two traps alone cannot.

Four fixtures appear in results but not in `evals/fixtures/`: `work-a-ticket`, for a skill
that worked one ticket, which OutcomeBound does not ship; `ready-ticket-on-provisional-blocker`,
for the same skill's earlier text (E13, E14); and the two judge-scored decision probes (E11),
whose reading the `decision` fixture checks deterministically.

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
  and did not read the history; current run 2 read the history and failed the brief check.
- **decision-brief, first wording.** All three runs read the skill. Two wrote a sound brief by
  hand without option letters after reading `brief --help`, since drawing seemed to need a file
  in a repository they were told to leave unchanged; one drew with the renderer and never read the
  history.
- **decision-brief, second wording.** It says `outcomebound brief -` reads standard input and
  writes no file, letters the options, and names the history as due diligence. Every check passed
  in every run; two runs show the renderer's marks, one wrote the same shape by hand.
- **none.** small-fix, all three: the answer said plainly that `datelint` is not installed and so
  did not run, but not in the word `UNVERIFIED` the check reads. decision, run 1: a sound
  recommendation, read from the policy and the history, set out as a table with no lettered
  options or undo line. dirty-review, run 2: the contradiction named, the document called "the
  documentation", not `parser.md`.

Median tokens and seconds a run:

| Arm | small-fix | dirty-review | long-run | decision |
| --- | --- | --- | --- | --- |
| `earlier` | 9,425 / 44 s | 11,417 / 47 s | 28,159 / 68 s | 14,465 / 47 s |
| current, core skill only | 9,897 / 42 s | 9,017 / 31 s | 34,576 / 70 s | 13,625 / 37 s |
| decision-brief, first wording | 15,299 / 37 s (n=1) | 19,144 / 47 s (n=1) | 20,193 / 54 s (n=1) | 16,894 / 61 s |
| decision-brief, second wording | — | — | — | 17,772 / 65 s |
| `none` | 8,072 / 41 s | 9,725 / 35 s | 19,119 / 70 s | 17,204 / 53 s |

### Skill fixtures

gpt-6-sol, medium effort, codex, 3 runs a cell, 2026-09-29. The `current` arm carried the kernel,
the four default skills, and for `slice-a-spec` and `work-a-ticket` also `slice-tickets` and a
ticket-working skill.

| Fixture | current | none | What differs | Median tokens, current / none | Median seconds |
| --- | --- | --- | --- | --- | --- |
| slice-a-spec | 3/3 | 0/3 | without the skill every run wrote two drafts split along a module line (command line, renderer), neither in the block the lint reads; with it, one draft each time, passing the lint | 23,189 / 21,418 | 64 / 67 |
| test-worth-keeping | 3/3 | 1/3 | all six new tests failed without the fix; two runs without the skill did not say the calendar test was failing before they began | 24,318 / 10,987 | 48 / 41 |
| unclear-outcome | 2/3 | 0/3 | every run showed the due dates and kept all five reminders; without OutcomeBound all three built "refuse the sixth" unsaid; with it two put the cap as a brief and built none, one built "refuse the sixth" unsaid | 31,672 / 15,326 | 99 / 57 |
| work-a-ticket | 2/3 | 2/3 | no difference: all six did the work in bounds; one run in each arm reported no evidence record, the `current` one no closing note either | 35,098 / 36,747 | 102 / 95 |

The unclear-outcome runs were graded twice from their kept repositories: by a check that required
a brief and no cap built, and by the check described under Scoring. The counts are the same.
Across all twelve runs a side, the means were 27,039 against 21,361 tokens and 76.5 against 64.8
seconds.

### The ladder

gpt-6-sol, medium effort, codex, 3 runs a cell, 36 runs, 2026-09-30, no call errors. Verdicts are
the required claims; the other columns are medians of what each run's footprint and the runner
recorded. The `current` and `unsized` arms here are not exactly an install: each fixture's note
said to read the core skill before planning, where an install points to it only "when unsure how
much design, testing, review or process a task needs", and they carried no project-facts block.

| Rung | Arm | Pass | Process documents created | Lines added | Tokens | Seconds | Full-suite runs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1, a misspelt word | current | 3/3 | 0/3 | 1 | 11,506 | 64 | 1 |
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

- Every probe passed in every run: all 36 made the change correctly. Every failure is the
  no-process-document claim. Rung 4 does not require the absence of a process document, since a
  risky change can warrant one.
- Every process document recorded is a new file under `docs/design/` or `docs/decisions/`.
  Without OutcomeBound, every rung-4 run and one rung-3 run wrote both.
- Seven of the nine rung-2 answers cite `CONTRIBUTING.md`.
- Every run ran the slow full suite at least once. No run committed, and no run put a question to
  the person.
- The install arms ran focused tests about twice as often. Median focused test runs (commands
  naming `unittest`, `pytest` or `test_`): rung 2, 4 with `current` and with `unsized` against 2
  without OutcomeBound; rung 3, 4 and 3 against 1; rung 4, 4 and 4 against 3; rung 1, 1 in every
  arm.
- The nine rung-4 workspaces were graded again by the probe that compares every SKU, name and
  quantity: all still pass.

### The ladder rerun

gpt-6.1-sol, medium effort, codex, 3 runs a cell, 12 runs, 2026-09-30, no call errors. The
`current` arm wrote the project facts and pointers adopt writes in place of the note's line
sending the model to the core skill, so it is the install. Its kernel text is the one the tree
ships, apart from the version in the block's marker; its four skill files are the texts of
2026-09-30, of which `gather-requirements` and `tests-worth-keeping` are unchanged since, while
`decision-brief` and `using-outcomebound` have changed a few words naming the launcher and what
`outcomebound home` prints. The facts include the line that process a project
document only suggests is sized like any other step. Rung 2 also fails a run that runs the slow
integration suite. The two arms ran at commits that differ only in research text.

| Rung | Arm | Pass | Process documents created | Lines added | Tokens | Seconds | Ran the full suite |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2, a two-character bug | current | 3/3 | 0/3 | 7 | 20,356 | 79 | 0/3 |
| | none | 0/3 | 3/3 | 23 | 16,309 | 94 | 3/3 |
| 3, a new option across two modules | current | 3/3 | 0/3 | 61 | 14,838 | 104 | 1/3 |
| | none | 0/3 | 3/3 | 90 | 16,249 | 131 | 3/3 |

Every run in both arms made the change correctly, and every run in both arms added a test, so a
regression test does not separate them. With OutcomeBound, every rung-2 answer labelled the slow
suite `UNVERIFIED` with the reason it was skipped and said the design note and second reader were
not needed for a fix its checks cover. Without it, every run wrote a design note (and on rung 3 a
decision record too), ran the slow suite, and asked for the second reader `CONTRIBUTING.md`
suggests. No run committed or put a question to the person. The install arm ran focused tests
more and the slow suite less: median focused test runs 4 against 2 on rung 2 and 3 against 1 on
rung 3. Its answers were longer: median 96 against 79 words on rung 2, 78 against 59 on rung 3.

### Judge-scored decision probes

gpt-6-sol, medium effort, codex, judged by gpt-6-sol with the rubric withheld from the candidate,
3 runs a cell. The project and prompt are the `decision` fixture's. Arms: the core skill with its
section asking for the checking before a decision is put to the person, and the core skill
without it. The deterministic check, that the workspace was left unchanged, passed in all twelve.

| Probe | Date | With the section | Without it | What differs |
| --- | --- | --- | --- | --- |
| fact in reach: `docs/compatibility.md` and `CHANGELOG.md` settle it | 2026-09-24 | 3/3 | 0/3 | every run without the section still read the files that settle the decision; all three failed on the brief's form (an id, lettered options, a recommendation with its reason), and the judge found one of them also did not rest its recommendation on those files |
| fact in history: only `git log` shows a 60-second default tried and reverted because a gateway closes connections after 45 seconds | 2026-09-25 | 2/3 | 0/3 | every run without the section read the history and found the revert, failing only on the brief's form; the one failure with it never read the history |

The fact-in-reach runs worked in a directory named after the scenario, which the model could
read. Three further runs of the with-section arm on 2026-09-25, in workspaces no longer named
after the scenario and judged against the later rubric, also passed 3 of 3, so the directory name
does not explain that arm's result. Both probes' prompts carried the line "Do not ask clarifying
questions; state the assumptions you proceed on." A probe run took 32 to 49 seconds.

### Judge-scored probes of a ticket-working skill

A skill for working one ticket, which OutcomeBound does not ship, on one fixture not in
`evals/fixtures/`: `ready-ticket-on-provisional-blocker`, where the engine lists a ticket as ready
while its blocker awaits only a person's confirmation. A deterministic post-check read whether
the ready ticket was claimed and its bug fixed; a gpt-6-sol judge read the answer against a rubric
withheld from the candidate. codex-cli 0.156.1. In the first three rows both arms were probed (the
prompt asked the model to name and quote the instruction behind any stop), so they are
diagnostics, comparable only with each other. Cells read gpt-6-sol / gpt-6-luna where a row ran
both.

| Change to the skill | Date | Model, effort | Runs | Post-checks pass | Refused the ready ticket | Stopped on a branch, unmerged | Judged PASS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before: the skill says work such a ticket; its reference's claim rule wants every blocker closed | 2026-09-24 | sol medium / luna max | 3 / 3 | 3/3 / 1/3 | 0/3 / 2/3 | 3/3 / the 1 run that did the work | 0/3 / 1/3 |
| the claim rule brought into agreement | 2026-09-24 | sol medium / luna max | 3 / 3 | 3/3 / 3/3 | 0/3 / 0/3 | 3/3 / 3/3 | 1/3 / 2/3 |
| the skill lets the project's own fast-forward land the work | 2026-09-24 | sol medium / luna max | 3 / 3 | 3/3 / 3/3 | 0/3 / 0/3 | 0/3 / 0/3; all six landed | 1/3 / 1/3 |
| wording audit: one sentence reworded, one repeated sentence removed; unprobed, questions allowed | 2026-09-25 | luna max | 5 a side | 5/5, 5/5 | 0/5, 0/5 | — | 4/5 before, 5/5 after |
| audit baseline before any edit; unprobed, with the no-questions line | 2026-09-25 | sol medium | 3 | 3/3 | 0/3 | — | 3/3 |

- The two luna refusals quoted both contradicting sentences (E13).
- The answers that stopped short quoted the skill's list of acts that "always stop a run" (E14):
  seven of the twelve probed answers before the fast-forward change named that sentence. After it,
  three of six named the skill's end-of-scope reporting line instead, and none stopped short.
- The judge's verdicts are not the table's. Its rubric listed a policy gate as unnecessary while
  the skill required the verify and audit steps that gate named, and it cited that item against 10
  of the 18 probed runs, alone in 6 whose post-checks passed (lesson 12).
- In the wording audit the one failing run did all the work and passed every post-check; the
  judge called the closing question in its answer, asking the person to confirm the blocker, an
  unnecessary stop, while two passing runs on the same side ended with the same kind of question.
  The one-run difference came from the judge's reading, not from either edit, and reads
  `UNVERIFIED`.
- The audit baseline was one arm of an instruction audit whose matching after arm never ran; with
  it, three runs of the fact-in-reach decision probe passed 3 of 3 (above).
- Run times: gpt-6-luna at max effort took 238 to 701 seconds a run on this fixture, against 104
  to 136 for gpt-6-sol at medium.

### The hand-off comparison

Run 2026-10-03, codex-cli 0.160.0, the `current` arm, 63 runs, every one at one clean commit; no
call failed. The fixtures, the cells and the reading rules, written before any run, are in
`evals/README.md`. Three bases (`duration`, `invoice`, `tags`), three repetitions each, so a cell
is 9 runs; the counts below are verdict PASSes, with the per-base counts after them.

| Implementer (its tier) | `ticket` | `design` | `spec` | `full` |
| --- | --- | --- | --- | --- |
| gpt-6-astra high (outcome) | 9 (3, 3, 3) | | 9 (3, 3, 3) | |
| gpt-6-sol medium (design) | 9 (3, 3, 3) | 9 (3, 3, 3) | | |
| gpt-6-luna xhigh (spec) | 6 (3, 3, 0) | | 9 (3, 3, 3) | 6 (3, 3, 0) |

`within-bounds`, `project-tests-pass` and `eval-files-unread` passed in all 63 runs; every
failed verdict failed `acceptance` only. In the 18 `spec` runs, `package-tests-pass` and
`package-tests-unchanged` passed in all 18. No run read the hand-off or slicing skills
(`guidance_reads` 0 in all 63).

All six failures are one row of the `tags` ticket: "Any other number of fields is the read error
it is today." gpt-6-luna widened the message to `expected 4 or 5 fields, found 3` in each of the
six `ticket` and `full` runs; gpt-6-astra and gpt-6-sol kept it in all their `ticket` runs. The
spec package's step says to raise the error "with the same message", and gpt-6-luna kept it in
all nine `spec` runs.

Read by the rules:

1. The design package on gpt-6-sol: its `ticket` cell has 9, so a gain cannot show. No
   headroom: inconclusive. Nothing is cut on this result.
2. The spec package on gpt-6-luna: 9 against 6, a gain of 3, so by rule 1 the package helps.
   The whole gain is one row on one base, the same in all six runs it failed, so it shows that an
   exact sentence in the package reached a detail the ticket's own words left to the implementer.
   It does not show a gain spread over many kinds of detail.
3. The spec package on gpt-6-astra: 9 against 9, no drop, so it does not support the hypothesis
   that the package makes an outcome-tier implementer overfit. The rows the package's tests leave
   out (listed in `evals/README.md`) passed in all nine.
4. `--detail full` on gpt-6-luna: 6 against `spec`'s 9, so it does not beat the spec package.
   `--detail full` and its three fixtures were removed, as the tickets design says.
5. Noise: gpt-6-luna `ticket` against `full` is 6 against 6, the same failure in the same runs.
   The spec package's difference of 3 exceeds it.

Median tokens per base (`duration`, `invoice`, `tags`): gpt-6-astra `ticket` 25,643, 22,361,
30,595, `spec` 22,039, 17,337, 22,519. gpt-6-sol `ticket` 16,605, 24,095, 32,770, `design`
23,813, 22,189, 25,201. gpt-6-luna `ticket` 27,960, 36,817, 49,004, `spec` 19,860, 28,142,
34,855, `full` 33,997, 38,748, 55,699. Median seconds: gpt-6-astra `ticket` 109.5, 140.4,
170.2, `spec` 65.4, 58.9, 106.9; gpt-6-sol `ticket` 76.9, 97.4, 145.9, `design` 110.5, 119.0,
132.3; gpt-6-luna `ticket` 144.5, 124.8, 216.3, `spec` 101.3, 70.2, 120.2, `full` 146.3,
211.4, 294.7. The spec package, which carries most of the solution, cost fewer tokens and
seconds on both models it ran on; the token and second counts never change a verdict.

Scope: one implementer a tier, all three from one maker and one harness, three small bases in
one repository, nine runs a cell, which shows only a large effect; a PASS shows only what its
check reads, for that model on that day.

### Results not kept here

- **Twelve `none` runs refused at setup** (2026-09-29; lesson 11): no model ran and no verdict
  exists.
- **A harness self-test** with a stand-in for codex that runs no model: it checks the runner's
  plumbing, not a model.
- **Proposal-only samples from before the fixtures** (2026-08-23 to 2026-08-30): a model described
  the approach it would take to written scenarios, with each scenario's expected answer withheld,
  and nothing was executed. The samples matched their rubrics 7 of 7, 2 of 2 and 9 of 9 (the
  first two with backend and effort not recorded, the third gpt-5.6-sol at medium; all three
  scored by the session that dispatched them), and 0 of 1 under a Claude Opus judge (codex-cli
  0.151.0, gpt-5.6-sol at medium). That judge scored a "goal envelope" as unnecessary in an answer
  that proposed only a focused regression test and a local fix under Outcome, Context and Bounds
  headings: it matched a mechanism's words, not its presence. They show which mechanisms a model
  names when asked, not the diff, the bounds or the cost (lesson 13).
- **The slicing arms' breakdowns**: their sizing findings are in
  [`work-breakdown.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/work-breakdown.md).

## What the results support, and what they do not

**Supported, each on one model, three runs a cell, one small repository a fixture:**

- On the core fixtures, OutcomeBound's text changed the report's vocabulary and shape, not
  whether the work was right or the bounds held (E1, E2).
- A skill's wording decided its fixture's result: one wording of decision-brief scored below
  having no skill, another scored 3 of 3 (E3).
- slice-tickets changed the cut of one small design from two tickets along a module line to one
  (E4).
- tests-worth-keeping changed whether the report named a failure that predates the work, and
  gather-requirements whether a reversible choice was named or put to the person (E5).
- On the smallest ladder task the install stopped process documents; with the project facts'
  suggested-process line, on a newer model, it stopped the process a project's documents only
  suggest on the two middle tasks, the slow suite included, where the same model without it
  followed every suggestion (E7, E10). The rerun's `none` arm ran on the same model, so the
  difference is the text, not the model.
- In probed diagnostics of a skill OutcomeBound does not ship, a contradiction between a skill
  and its reference file stopped the smaller model and not the larger, and a stop rule that named
  a merge to the default branch stopped every run that did the work (E13, E14).

**Not supported, or not measured:**

- **Underengineering.** No fixture yet separates the arms (E8): the model sized the one planted
  risk right on its own. Whether OutcomeBound's text prevents fragile or unchecked work is
  unmeasured. The engine's deterministic checks (the floor, the finish check) are tested by the
  suite, not by these evals.
- **The sizing paragraph.** Its effect is `UNVERIFIED` (E9); three runs a cell cannot show a
  small one, and it has run on one model.
- **Effect sizes.** Three runs a cell shows a large difference, not its size, and not a
  difference of one run in either direction.
- **Other models, efforts, harnesses and repositories.** One model at medium effort through codex
  for every deterministic pass, with gpt-6-luna at max effort only in the judge-scored
  diagnostics; each family's fixtures are one synthetic repository.
- **Whether a brief's recommendation follows the evidence.** The decision fixture's brief check
  reads the form; the transcript checks read that the documents and history were opened, not
  that the recommendation rests on them.
- **The shipped skill texts, except in the ladder rerun.** Each result is for the bytes its arm
  installed, recorded as digests. Every run from the decision-brief passes on carried the kernel
  text the tree ships; the first core pass's kernel differed in punctuation and had no pointer to
  the decision-brief skill. The skill-fixture pass installed `gather-requirements`,
  `slice-tickets`, `tests-worth-keeping` and `using-outcomebound` in texts that differ from the
  shipped ones, and the first ladder pass a different `using-outcomebound`; only the rerun
  installed all four default skills, in their texts of 2026-09-30, of which `decision-brief` and
  `using-outcomebound` have since changed a few words naming the launcher. The `decision-brief`
  text of that day ran in the
  skill-fixture and ladder passes, where no check reads a brief, but not on the `decision`
  fixture.
- **Asking the person.** No ladder run put a question to the person in any arm, so the ladder
  says nothing about unnecessary questions.
- **Turns.** Tokens, seconds and commands are recorded; turns are not.
- **Resumption.** `long-run` asks for progress kept resumable but runs as one call; no run is
  interrupted and resumed in a fresh session, so carrying work across sessions is not measured.

**Confounds each result carries:**

- Ladder rungs 2 and 3 measure a suggestion the fixture's note points at, not an unprompted habit:
  the note names `CONTRIBUTING.md` as how changes are reviewed, which a model can read as the
  project's instruction, and OutcomeBound puts a project's own instructions first. No fixture yet
  pairs this with a project whose process is required, where following it is the right answer.
- The first ladder pass's install arms carried a note line sending the model to the core skill
  unconditionally and no project-facts block; the rerun's install arm carried what adopt writes.
- The `none` pass ran later the same day at a later commit than the passes it is compared with,
  whose install carried two skills, not the four an install carries.
- The `earlier` arm installs the checkout's own core skill, so it is the earlier kernel with the
  current skill; an `earlier` run made with a core skill that points to decision-brief is not
  comparable with the runs here.

**Open questions**, from the independent reviews listed under Sources and from the limits
above:

- A fixture a capable model gets wrong alone on underengineering: a risky change whose obvious
  fix skips the check its risk needs, taken from a failure an agent was observed to make.
- A second model, and a cheaper one, on the fixtures that separate the arms.
- A required-process case beside the suggested-process one.
- The sizing paragraph at more runs a cell.
- For decisions: whether the recommendation follows the evidence, scored apart from whether the
  brief went through the renderer.
- Unnecessary questions and repeated checks, scored beside correctness.
- Real changes in place of synthetic repositories: past changes to a product codebase replayed
  from their parent commits under each arm, graded by the tests and fixes that landed after them.
- Paired tasks with the same outward act, authorised in one and not in the other, so needless
  escalation and unauthorised execution are scored apart; and tool calls, interruptions of the
  person and defects that escape, recorded beside tokens and seconds.

## What published research adds

The results above rest on a judge of the candidate's own family and on three runs a cell.
Published studies say how far either can be trusted, and what another judge, more runs or more
tasks buy:

- **Model judges** — consistency against validity, a verdict's variation between identical calls,
  a changed judge as a new measurement, self- and family preference, reasoning effort and
  optimisation pressure, criteria drift, and judging many model-drafted labels at once: in
  [llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md). The judged probes here used the configuration those studies
  warn about, a judge of the candidate's own family (E15; lesson 12).
- **Statistics, power and task selection** — pass^k, standard errors and paired comparisons,
  infrastructure and time-of-day noise, choosing tasks that can move, and references or single
  database states that are wrong: in [agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md). The power figures for this
  suite's own design are under Runs per cell and power above.
- **Error analysis** and **what other evaluation tools ship**: in
  [agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md).

## Lessons on eval design

1. **A fixture a capable model gets right alone cannot separate the arms.** Such a fixture guards
   against a change making things worse and measures nothing more (E2, E8). To show an effect,
   pick tasks the model gets wrong without the text, and say which ones those are.
2. **Include tasks where the text should add nothing.** Fixtures chosen for the baseline to fail
   bias the result toward the text; ordinary tasks in the middle of a ladder show what it adds
   where it should add nothing, and a curve across tasks shows whether effort follows need (E7).
3. **Separate substance from report shape.** Check the work by running it and the report by
   reading it, and say which kind failed. A check that reads one word (`UNVERIFIED`, a file name)
   measures vocabulary; that is worth measuring when the vocabulary is the point, and misleading
   when it stands in for the work (E1).
4. **Grade with what the model cannot change.** Protect graders, baselines and the documents
   checks rely on; hash them before and after; read the seed commit before the model runs, since a
   tag in the workspace can be moved. A test file the model may edit can be weakened until it
   passes; a protected probe judging the fix cannot. Count the model's effects from the
   filesystem, not from Git state the model can set: `git diff` and `git status` honour the
   index's assume-unchanged and skip-worktree bits, so `git update-index --assume-unchanged
   <file>` hides an edit from both (`git ls-files -v` marks such entries with a lowercase letter
   or `S`), and a `.gitignore` that ignores itself hides new files from `git status -uall`. In one
   harness (O) a scope grader reported no change in five distinct ways while the model had changed
   something (E16): a rewritten grader hidden by an index bit; a file name holding a newline, which
   `find -print` split so that `git hash-object` failed on both halves and two empty digests
   compared equal; an unreadable (mode 000) file that collapsed the same way; a tracked file
   replaced by a symlink, and a new symlink, which `-type f` never listed; and entries skipped by
   name before their kind was checked, such as a symlink named like bytecode
   (`__pycache__/x.pyc`) and the `.git/hooks/` directory. What held was one shared walk with
   `lstat` over raw byte names that lists symlinks without following them, counts an unreadable
   or non-regular entry as a change, gives no verdict when the walk itself fails, ships among the
   protected files hashed before the run, states what it does not watch (Git's own object and
   ref files), and is tested with each of those cases planted as a fixture it must count.
5. **Treat everything in reach as part of the prompt.** Graders in the workspace get read (E12).
   A working directory named after the scenario tells the model what is being tested. A fixture
   note that sends the model to a skill unconditionally is a stronger arm than an install whose
   pointer is conditional. A "do not ask questions" line forbids the very stop a fixture may be
   measuring. A probe asking the model which instruction it followed changes what it does, so a
   probed run is an arm of its own. A project's own documents steer the behaviour measured (ladder
   rungs 2 and 3): decide whether that is the question, and build the case where it is not. A
   fact meant to be found only in the history leaks through Git's plain-text copies:
   `.git/COMMIT_EDITMSG` holds the last commit message and `.git/logs/HEAD` each commit's subject
   (git 2.56.0, checked 2026-10-01). Delete the first, keep the fact out of subject lines, test that
   no plain file under `.git` outside `objects/` names it, and set a fixed author, committer and
   commit date inside the fixture's own setup, so the caller's `GIT_AUTHOR_*` and
   `GIT_COMMITTER_*` variables cannot change the seed commit; built under bash 5 with GNU sed,
   bash 3.2 with BSD sed, and with those variables set by the caller, one such fixture made the
   same seed commit each time (O, 2026-09-24). On the judge's side, parse its verdict so the
   answer being judged cannot supply it: inspect-ai's model grader binds to the last `GRADE:` in
   the judge's output, so a grade echoed in its reasoning or planted in the submission does not
   win (L, [inspect-ai, model-graded scorers](https://inspect.aisi.org.uk/model-graded.html), read
   2026-10-01).
6. **An arm is the bytes it installs.** Record the digest of every file an arm writes, flag runs
   that differ, and treat a changed skill as a new arm. Make the install arm write what the
   installer writes, pointer conditions included. Make the no-text arm free of user-level
   context: the operator's configuration, rules, memories, Git configuration and credentials,
   and check the transcript for user-level files the harness read anyway (codex read agent role
   files under its isolation flags; Arms, above).
7. **Make each check as strict as the contract, no stricter.** Accept every behaviour the text
   allows (a reversible reading built and named as a choice); require only what the check is for;
   observe, rather than require, what an older arm was never asked for; check a stated contract in
   full (every row that must survive, not only the column that changed); let the verdict and its
   observations share one rule. When a check changes, grade the kept runs again and report
   whether the counts moved.
8. **Record what a run did beyond the verdict.** The footprint, tokens and seconds show size and
   cost where a pass rate cannot, and an observation can become a required claim when it proves
   to matter, as the slow-suite run did on rung 2.
9. **Change one thing at a time, or run the baseline again.** When the model changes between
   passes, run the no-text arm on the new model before crediting the text (E10).
10. **State what three runs can show.** At three runs a cell only a difference like 0 of 3 against
    3 of 3 is worth reading; compute power before choosing repetitions, and give each result the
    smallest difference it could detect.
11. **Count the cost before running.** Calls are arms × fixtures × repetitions: 33 an arm for
    the eleven fixtures, 36 for the ladder's three arms. The median run of a cell here took 8,000
    to 37,000 tokens and half a minute to three minutes. A failed call is recorded, never retried,
    so a pass's count stays whole; a silent retry would also shift what is measured, since inputs
    that fail on a bug and pass on a re-roll get more chances than the rest (L, [inspect-ai,
    handling errors](https://inspect.aisi.org.uk/handling-errors.html), read 2026-10-01). Count
    only calls that completed: a post-check run on a workspace whose model call failed describes
    the leftover fixture, not a decision. Before a pass, drive every fixture through every arm with
    a stand-in for the model: a `none` pass whose fixtures protected skill copies that arm does
    not install refused all twelve of its runs at setup.
12. **Prefer deterministic checks to a model judge, and know what each costs.** A judge of the
    candidate's own family, with agreement with a person unmeasured and a rubric that can fall out
    of step with the text, is weaker evidence than a check that reads the tree; a deterministic
    check reads only what it was written to read. Here a rubric out of step with the skill under
    test listed a policy gate as unnecessary while the skill required the verify and audit steps it
    named: the judge cited it against 10 of 18 probed runs, alone against 6 whose deterministic
    post-checks passed (O, 2026-09-24), and agreement with a person was measured on none of the 46
    judged runs (O, 2026-09-24 and 2026-09-25). A judge that matches a mechanism's words rather than
    its presence turns an answer's framing into a finding (Results not kept here). Before crediting
    a judged difference of one run to the text, read the answers on both sides (E15).
13. **Execute, do not ask for a plan.** A run that only proposes an approach tests which
    mechanisms the text names, not the diff, the bounds or the cost; the work has to be done in a
    repository for those to be measured. Asked only for a plan, with its tools in an empty
    directory, an agentic model searched it for the repository the task named until the prompt
    said there was none (codex, 2026-08-30).
14. **Keep the evidence, cite the counts.** Kept fixture repositories let a changed check be
    re-run without new calls; kept transcripts let a count like E12 be taken after the fact.
15. **Do not judge text on the fixture it was written from.** An addition drafted after reading a
    fixture's runs is tuned to that fixture, which can no longer judge it fairly; judge it on
    another fixture that exercises the same behaviour, or build one (reasoning).

## How to run the evals here

[`evals/README.md`](../evals/README.md) is the reference: prerequisites (a codex ChatGPT
login, a clean checkout), the arms, each fixture's claims, and reading a
result. In short:

```bash
MODEL=<model>   # one model for every run; a run without --model is refused
python3 evals/run.py --arm current --model "$MODEL" --repetition 1 \
  --fixtures ladder-2-last-units,ladder-3-reorder-list
python3 evals/run.py --arm none --model "$MODEL" --repetition 1 \
  --fixtures ladder-2-last-units,ladder-3-reorder-list
python3 evals/run.py --summary evals/results/raw
```

Repeat each for repetitions 2 and 3. `--effort` sets codex's reasoning effort (default
`medium`); `--out` names the run directory (default `evals/results/raw/<id>/`, ignored by Git);
`OUTCOMEBOUND_FIXTURE_ROOT` keeps fixture repositories outside any Git checkout. Compare arms
within one fixture and one model.

## Sources

- **Fixtures:** [`evals/fixtures/`](../evals/fixtures/): `small-fix`, `dirty-review`,
  `long-run`, `decision`, `unclear-outcome`, `test-worth-keeping`, `slice-a-spec`, the four
  `ladder-*` rungs and their shared `ladder/` (`base.sh`, `footprint.py`,
  `no_process_document.py`, `cli_probe.py`). Runner: [`evals/run.py`](../evals/run.py).
- **Run records**, kept outside the repository, each run's prompt, answer, transcript and
  metadata as `evals/README.md` describes:

  | Pass | Date | Model | Runs |
  | --- | --- | --- | --- |
  | Judge-scored decision probes | 2026-09-24, 2026-09-25 | gpt-6-sol | 12 |
  | Ticket-skill probes, probed, before and after two skill fixes | 2026-09-24 | gpt-6-sol medium, gpt-6-luna max | 18 |
  | Ticket-skill wording audit, unprobed, questions allowed | 2026-09-25 | gpt-6-luna max | 10 |
  | Audit baseline, decision probe and ticket fixture | 2026-09-25 | gpt-6-sol | 6 |
  | Core fixtures, `earlier` and current | 2026-09-29 | gpt-6-sol | 24 |
  | Core fixtures, decision-brief first wording | 2026-09-29 | gpt-6-sol | 6 |
  | Decision fixture, decision-brief second wording | 2026-09-29 | gpt-6-sol | 3 |
  | Core fixtures, `none` | 2026-09-29 | gpt-6-sol | 12 (and 12 refused at setup) |
  | Skill fixtures, `current` and `none` | 2026-09-29 | gpt-6-sol | 24 |
  | Ladder, `current`, `unsized` and `none` | 2026-09-30 | gpt-6-sol | 36 |
  | Ladder rerun, rungs 2 and 3, `current` and `none` | 2026-09-30 | gpt-6.1-sol | 12 |

  163 model runs in all: 117 graded by deterministic checks alone, and 46 judged by a model beside
  deterministic post-checks. Token counts for the 2026-09-29 passes are read from each
  transcript's final `tokens used` line, as `--summary` reads them. The judge-scored runs are
  kept as committed result files, with raw answers and judge replies for the decision probes and
  the probed ticket-skill runs; the proposal-only samples of 2026-08 are kept as result files.
- **Reviews:** two independent readings of these results (Fable 5.1 at high effort; gpt-6-astra
  at medium effort through codex) contributed the limits, open questions and lessons above.
- **Published sources**, each read 2026-10-01: inspect-ai, model-graded scorers,
  <https://inspect.aisi.org.uk/model-graded.html>, and handling errors,
  <https://inspect.aisi.org.uk/handling-errors.html>; the two-agent context-file ablation,
  <https://arxiv.org/html/2607.27250>; Codex authentication, <https://learn.chatgpt.com/docs/auth>;
  Codex agent approvals and security, <https://learn.chatgpt.com/docs/agent-approvals-security>.
  The studies on judges are listed in [llm-as-judge.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/llm-as-judge.md#sources), those on
  statistics, task selection, error analysis and tools in [agent-evals.md](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/agent-evals.md#sources).
- **Related records:** [`writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md) §9 (how to
  measure a change to model-facing text, with detection power);
  [`prompt-standard.md`](prompt-standard.md) S11 (remove one group of lines at a time and
  re-run); [`harnesses.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/harnesses/cross-harness.md#131-one-practitioners-account-t1t7) §13.1, T1 (instruction files
  shrink; a skill should be tested by eval); [`work-breakdown.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/work-breakdown.md) (the slicing
  arms).
