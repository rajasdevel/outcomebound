---
last_checked: 2026-09-26
volatility: STABLE (measured studies, the §3 ledger counts and the §4 slicing runs) / VOLATILE (F1 horizons by model, F6 vendors' published sizes, newest-model claims in F5 and F13)
sources:
  - https://arxiv.org/html/2503.14499v1
  - https://metr.org/time-horizons/
  - https://metr.org/notes/2026-01-22-time-horizon-limitations/
  - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
  - https://www.anthropic.com/engineering/harness-design-long-running-apps
  - https://developers.openai.com/codex/use-cases/follow-goals/
  - https://developers.openai.com/blog/run-long-horizon-tasks-with-codex
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
  - https://www.anthropic.com/research/measuring-agent-autonomy
  - https://docs.factory.ai/missions/overview
  - https://arxiv.org/html/2608.09802v1
  - https://arxiv.org/abs/2601.13295
  - https://arxiv.org/abs/2512.08296
  - https://static1.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf
  - https://arxiv.org/abs/2607.07593
---

# Work breakdown for coding agents

Re-check when METR or another evaluator publishes a horizon for a new model, a lab or harness
vendor changes its task-size guidance, or a forecast's horizon passes (2027-03-31 for TS1–TS3).

How large a unit of work handed to a coding agent should be, who cuts it, what each ticket costs
the person, and how to write one that a person accepts and a smaller model builds from.

This reference answers how work handed to a coding agent should be cut: how large a task or ticket
should be, what pushes it smaller or larger, what each ticket costs the person who accepts and
closes it, who should do the decomposing, how the right unit moves with each model generation, and
how to write a ticket that a person reads and accepts and a smaller model can build from. It is for
anyone who slices a spec into tickets, writes a slicing skill, designs a ticket layer, or hands
long work to an agent and wants it to run unattended without the person drowning in ticket
logistics (accepting, sequencing, re-accepting, closing and reconciling many small tickets).

**Evidence classes.** (M) measured, with models and sample named where they matter; a vendor's own
telemetry is (M, vendor). (L) guidance or a claim from a lab or tool vendor about its own models or
product. (P) practitioner consensus. (A) one person's view or one uncontrolled report. (F) a
forecast. (O) a result from this project's own ledger or runs. Where guidance was written for one
model generation, the text names it. `UNVERIFIED` marks what the evidence does not establish. Each
finding also carries a strength: **strong** (several independent measured results, or measurement
plus convergent guidance), **moderate** (guidance from several labs or vendors plus some measurement
or broad practitioner agreement), **weak** (one source, anecdote, or a vendor claim alone).

**Citations.** `[sizing-…-N]`, `[sizing-check-1]`, `[anthropic-17]`, `[openai-13]` and
`[latent-space-19]` resolve by `id` in [`_evidence/2026-09-26.jsonl`](../_evidence/2026-09-26.jsonl);
other bracketed ids resolve in [`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl). Each
record holds the claim as verified, a verbatim quote, the URL, the date and the evidence class;
a record the fact-check rewrote keeps its first wording in `original_claim`. Sources read without
an evidence record are cited by arXiv number or name. "One ticket ledger" means measurements taken
from one repository's own tickets: 165 issues created over five days, implemented by agents and
accepted by one person, with implementers' token counts, reviewers' verdicts and closing notes
recorded.

## Key findings

**P1. A ticket is an acceptance unit; milestones, sessions and commits live inside it, owned by
the implementer.** The person accepts an outcome once; the implementer keeps a plan with
milestones, runs each milestone in a context it can finish, and lands reviewable commits. Labs
have moved decomposition inside the handed-over task, and approvals decay as they multiply.
Moderate: convergent guidance from three labs and two vendors, practitioner convergence and
approval-decay telemetry; no controlled comparison. (L, M vendor, P) — F4, F7, §1.

**P2. Size a ticket as an outcome with a verifiable end state: bigger than one prompt, smaller
than an open-ended backlog.** Sources that give numbers point at hours to a couple of days of
human-equivalent work per acceptance unit (Devin 3 hours per session and 4–8 junior-engineer
hours per task, DORA hours to days, Codex goals running for hours), with longer outcomes cut at
milestones inside. The reliable single pass is shorter, about 1–3 low-context human-hours at 80%
success on early-to-mid 2026 models, which is why the milestones exist. Moderate for "hours, not
minutes"; weak for any exact figure, which is model-relative. (L, M) — F1, F6.

**P3. Put a floor under the ticket: it must be worth its fixed cost.** A change describable in one
sentence, proved by an existing test, or finishable in a handful of tool calls is a milestone or a
row inside a ticket, or a commit of its own, never a ticket. Findings, files and modules are not
ticket boundaries. Each fresh unit pays about half its tokens again to read the repository; in one
ticket ledger a three-line docstring cost about 261k tokens to implement and repair. Moderate.
(L, M, P, O) — F6, F8, F11, §3.

**P4. Set the ceiling by verification, coherence and reliability, not by what a reviewer reads in
one sitting.** A ticket may grow while it ends in a check the implementer can run (without one "you
become the verification loop" [sizing-lab-15]), its changes share one set of design decisions, and
its expected work fits the implementer's reliable horizon given internal milestones. Reviewability
is met by the landing unit (several reviewable commits or stacked pull requests), not by more
tickets. Moderate. (L, M) — F1, F3, F8, F9.

**P5. Cut acceptance boundaries only where a person's judgment is needed.** That is: an
irreversible or shared-system edge; a contract, schema or interface consumed outside the ticket; an
intent or scope decision not yet made; and a milestone reading on long work. Not per step, per
finding or per file. Otherwise the person is interrupted only for a destructive or irreversible
action, a real scope change, or input only they can provide [sizing-lab-27]. Moderate: lab
guidance, vendor telemetry, a small survey (n=21) and broad practitioner agreement. (L, M, P) —
F7, F12.

**P6. Split into parallel tickets only for independent writers on disjoint paths, each with its
own check.** Several agents writing one outcome lose reliability, conflict more and cost more
tokens. Strong for the cost of parallel writers; moderate for the independence conditions. (M) —
F9.

**P7. Chart only as far as knowledge is stable; let the plan inside the ticket be the living
part.** Pre-cut tickets encode design guesses that go stale and cost more to retry; an
implementer's plan file is revised as it learns. Settle intent before cutting; an open question is
its own unit. Moderate: one measured retry study and several consistent reports. (M, A) — F10, F4.

**P8. Build checkpoints into large tickets rather than splitting them.** Milestones each
finishable in one loop with a validation command, a progress file, progress claims audited
against tool results, and fresh-context verification at intervals. Moderate: lab guidance matched
to measured failure modes; the checkpoints themselves are not independently measured. (L, M) — F3.

**P9. Make the unit relative to the implementer and re-examine it every model generation.** Size
the execution unit to the implementer's reliable horizon; for a weaker implementer shrink the
milestones inside the ticket before shrinking the ticket; raise the ceiling when closed tickets
show the implementer did not need the split. Moderate. (L, M, A) — F5, F1.

**P10. The wording of the split rules, more than the work, sets the ticket count.** One spec sliced
by the same method came out at 5 to 54 tickets depending on which boundaries the rules allowed;
rules that split only at an edge, a decision the person must make first, or parallel work on
disjoint paths gave 5 and 7. Without a slicing guide, three of three runs cut one outcome into two
tickets along a module line. One project's own runs, one spec and one run per configuration.
(O) — §4.

**P11. Split rules without matching merge rules ratchet toward fragmentation.** In one ticket
ledger, four concrete split triggers faced one abstract merge rule, and the only merge signal (an
implementer reporting that a brief was unneeded) fired in 0 of 136 closing notes; a rule that every
later-found finding becomes its own ticket bypassed the floor and produced a batch of 35 tickets
with a median diff of 45 lines, whose briefs were longer than their diffs in 25 of 31. The
orchestrator then executed those 31 tickets as 6 groups. One ledger's counts. (O) — §3.

**P12. Most per-ticket confirmations a person is asked for are clerical.** Of 77 per-ticket
confirmations in one ledger, about 18–23 were judgments only the person could make; the rest were
facts a command reads (a CI run's conclusion, a tag on the remote, a label list), acts an agent or
reviewer had performed, or a triage file a lint could check. They were answered in bulk (one reply
became 36 records on 18 tickets), so a per-ticket confirmation carried no per-ticket judgment. One
ledger's counts; minutes per act are estimates. (O) — §3.

**P13. A ticket is read by two readers: lead with what the person decides, keep the detail the
implementer runs on.** Removing an issue's interface section cut solve rates by 33–40 points and its
requirements by 55–65; removing headers or flattening lists alone cost 10–30 (arXiv 2607.07593).
Readers scan headings and first words (NN/g). Put the outcome and the one question for the person
first, the decisions next, and reference material last. (M, P) — §5.

## 1. Three units, not one

The sources describe three different units, and most disagreement about "task size" dissolves once
they are told apart.

| Unit | What it is | Who cuts it, in the sources | What bounds it |
| --- | --- | --- | --- |
| **Acceptance unit** | What a person decides on: an outcome, a goal, a mission, a ticket | The person, with the agent proposing | The person's decisions: intent, irreversible edges, scope changes [sizing-lab-27] |
| **Execution unit** | What one context, loop or session does: a feature, a milestone, a sprint, one Ralph item | Increasingly the agent itself, in a plan file it maintains [sizing-lab-2, sizing-lab-5, sizing-lab-43, sizing-lab-59] | Context, compaction and error compounding; the model generation [sizing-trend-2, sizing-trend-3, sizing-lab-7] |
| **Landing unit** | What a reviewer reads and merges: a commit, a pull request, a stacked diff | The implementer, cheaply, because an agent does the git work [sizing-prac-10] | Review effectiveness and reviewability [sizing-review-1, sizing-review-8] |

In late 2025 and 2026 the labs moved the execution unit inside one handed-over task: one prompt
becomes an agent-written list of 200+ features consumed one per session [sizing-lab-2,
sizing-lab-3]; one sentence becomes a 16-feature spec over ten sprints [sizing-lab-5]; one spec
becomes a milestone plan run for about 25 hours [sizing-lab-43, sizing-trend-45]; one Mission
covers about 1–500 features behind one approved plan [sizing-lab-59]. Where a person is in the
loop, they approve a plan once, before execution [sizing-lab-53, sizing-lab-59]; in Anthropic's
harnesses nobody reviewed the agent-written list [sizing-lab-2]. In none of them does a milestone,
sprint or feature become a ticket.

A ticket system that makes every execution unit an acceptance unit charges the person for every
step. That is the likely mechanism behind over-slicing; no source tests it directly.

## 2. Findings

### F1. The reliable single-pass horizon is hours of low-context human work, far shorter than the headline — strong (VOLATILE)

- On METR's live data the 80% horizon is 4–10x shorter than the 50% horizon: Claude Opus 4.6 p50
  about 719 min against p80 about 70 min; Claude Mythos Preview (early) about 1,045 against 186;
  GPT-5.4 342 against 54; Gemini 3.1 Pro 384 against 90 [sizing-horizon-7, sizing-horizon-8] (M).
  In the original study 80% horizons were roughly 5x shorter [sizing-horizon-2] (M).
- METR's lead author warns that "a 50% time horizon of X hours does not mean we can delegate tasks
  under X hours", because reliability-critical, hard-to-verify work needs 98%+ success
  [sizing-horizon-11] (L). A constant-hazard fit of METR's 2025 suite put T80 near a third of T50,
  T90 near a seventh and T99 near a seventieth; its author's 2026 update says agents "probably
  don't obey a constant hazard rate" and that their hazard falls as a task goes on
  [sizing-horizon-24, sizing-horizon-25] (A, model fit). If so, reliability falls with length more
  slowly than exponentially, which weakens the case for cutting long work very fine.
- The p50 horizon has doubled about every 131 days since 2023 and about every 89 days since 2024
  [sizing-horizon-6] (M). At the frontier the number is hard to read: GPT-5.6 Sol's high cheating
  rate puts its horizon at 11.3 hours or above 270 depending on how cheating is scored, and METR
  calls none of these robust [sizing-horizon-16] (M); METR gave no horizon for Claude Opus 5.5
  [sizing-horizon-17].
- Time horizon measures task difficulty in human time, not how long the agent runs; agents are
  several times faster than humans on tasks they complete [sizing-horizon-10] (M).
- Horizons are measured on clean, low-context tasks. METR's task lengths are the time of a
  low-context contractor on self-contained, well-specified work; on five internal issues
  contractors took 5–18x the repository developers' own time, which METR says suggests horizons
  "may" correspond better to low-context labor [sizing-horizon-5, sizing-horizon-9]; messier tasks
  score lower [sizing-horizon-3]. METR's suite cannot measure above 16 hours reliably
  [sizing-horizon-9].

So one agent, in one unassisted pass, reliably (80%) completes work that would take a low-context
engineer roughly one to three hours, as of early-to-mid 2026 models on clean tasks. Longer runs are
real but rest on internal checkpoints (F3, F4), not on a longer single pass.

### F2. Success falls steeply with the spread of a change, even for one model — strong

- The same model, gpt-5.2, scores 72.8% on SWE-bench Verified, 41.2% on SWE-Bench ProMax (11.4
  files, 262 lines) and 22.9% on SWE-EVO (20.9 files, 610 lines) [sizing-horizon-29,
  sizing-horizon-30] (M). Unsolved SWE-EVO instances average 14.8 linked pull requests against 1.7
  for the easiest (arXiv 2512.18470).
- SWE-bench-Live (Claude 3.7 Sonnet): 48% on single-file patches under five lines, under 10% at
  three or more files or over 100 lines, none at seven or more files [sizing-horizon-27] (M).
  SWE-Bench Pro: resolve rates hold for one file and fall as the file count grows
  [sizing-horizon-28] (M).
- The dominant failure on large refactors is incomplete propagation: agents track the gold
  patches' file counts up to about five files, but 90% of their runs touch about ten files or fewer
  where the gold patches need about twenty [sizing-horizon-30] (M).
- Across 14,922 trajectories on five benchmarks, resolved runs concentrate at low spread (few
  files, small directory radius), low novelty (editing beats adding) and low centrality (few
  high-fan-in, high-churn modules) for every family and scale. How models succeed differs by
  family, not by strength: Claude matches the gold scope, Qwen exceeds it at every scale, though
  the two families ran under different harnesses [sizing-horizon-31] (M). No numeric cutoffs are
  published.

These are single-pass benchmark runs without an agent-owned plan or milestones. They bound the
execution unit (what one pass should touch), not directly the acceptance unit.

### F3. Long unattended runs degrade in specific, known ways — strong

- **Compounding.** Per-step accuracy falls as steps accumulate even when the plan and knowledge are
  supplied, partly because a model errs more once its own errors are in context (self-conditioning);
  scale does not fix it, thinking mitigates it [sizing-horizon-22] (M). A million-step task (Towers
  of Hanoi, synthetic) ran with zero errors by making every step minimal and independently voted;
  cost grows log-linearly in the step count, Θ(c·s·ln s) with one decision per agent, and
  exponentially in the decisions assigned to one agent [sizing-horizon-33] (M). Supervising the 16%
  of steps where an alternative flips the outcome beat supervising all of them (arXiv 2602.03412)
  (M).
- **Context.** Performance grows unreliable as input grows, with task difficulty held fixed, across
  18 models [sizing-horizon-26] (M). In one study 5x compression left completion unchanged but
  tripled re-fetching in one environment and not in another [sizing-horizon-34] (M); recurrent
  compression increased blocked actions and run-to-run instability in another
  [sizing-horizon-35] (M, preliminary). Anthropic's Fable 5.1 guide still lists compaction
  summaries dropping constraints and decisions as a known symptom [sizing-trend-18] (L).
- **Self-extension.** When agents keep extending their own code, the core pass rate falls from
  64.6% to 35.5% across checkpoints and no agent finishes any problem end to end
  [sizing-horizon-32, sizing-trend-22] (M).
- **Lock-in.** In one Claude Opus 4.6 run over 27 compactions, an early wrong architecture choice
  was never reversed; the rest of the run patched around it [sizing-trend-23] (M, one run).
- **Done is not done.** Claude 3.7 Sonnet passed the projects' own tests 38% of the time, but 0 of
  15 reviewed pull requests were mergeable as they stood [sizing-horizon-18] (M); reviewers would
  not merge about half of test-passing SWE-bench Verified pull requests [sizing-horizon-19] (M).
  o3 reward-hacked 43x more often on the suite whose scoring function it could see, which METR says
  is "perhaps" the reason [sizing-trend-21] (M).
- **Completion claims are not evidence.** In 67.9% of review runs an agent did not read every file
  it was asked to, and 80.4% of those final answers claimed or hid it; those agents missed planted
  defects 1.8x as often (arXiv 2609.20812) (M). A reviewer late in a long transcript misses a
  dangerous coding action 2–30x more often than when shown it alone (arXiv 2605.12366) (M).

The responses the labs ship are internal checkpoints, not smaller tickets: milestones "small
enough to complete in one loop" with validation and a stop-and-fix rule [sizing-trend-45];
fresh-context verifier subagents at intervals [sizing-trend-32]; auditing each progress claim
against a tool result, which "nearly eliminated fabricated status reports" in Anthropic's testing
[sizing-trend-31]; periodic fresh starts against drift [sizing-trend-11] (all L).

### F4. Decomposition has moved inside the handed-over task — moderate

- Anthropic, November 2025: an initializer agent turned one prompt into 200+ features, and each
  later session did exactly one, with a progress file and git commits [sizing-lab-1 to
  sizing-lab-3] (L). Self-evaluation was the weak point, and a context reset beat compaction for
  that model.
- Anthropic, March 2026: a planner turned a one-sentence prompt into a 16-feature spec over ten
  sprints; generator and evaluator negotiated per-sprint contracts with no person in that loop
  [sizing-lab-5, sizing-trend-6] (L). Without the planner the generator under-scoped
  [sizing-lab-6] (L).
- OpenAI: a GPT-5.3-Codex run, prompted to write its own milestone plan from the author's spec, ran
  about 25 hours uninterrupted, 13M tokens, 30k lines [sizing-lab-43, sizing-trend-44,
  sizing-trend-45] (A, one run); the ExecPlan template tells the agent not to ask the user for next
  steps between milestones [sizing-lab-45] (L); OpenAI describes the person "steering at milestones
  instead of micromanaging every line" as the aim, not what that run did [sizing-lab-44] (F).
- Factory: one Mission is an agent-orchestrated plan of features and milestones, about 1–500
  features as "a planning heuristic, not a hard limit", with the person approving the plan
  [sizing-lab-59] (L); the median mission runs about 2 hours against about 8 minutes for an
  interactive session, and 14% run over 24 hours [sizing-prac-31] (M, vendor).
- Claude Code: `/batch` splits one instruction across 5–30 subagents in worktrees [sizing-lab-18];
  `/goal` lists "working through a labeled issue backlog until the queue is empty" as one goal
  [sizing-lab-22] (L). Google Antigravity tells users to direct the primary agent to spawn
  concurrent subagents for large sweeps [sizing-lab-62] (L).
- Practitioners converge from the other side: Ralph runs one item per loop, but the agent picks the
  item from a plan file the person curates and "throw[s] out often" [sizing-prac-18,
  sizing-prac-19] (A); an Amp engineer shipped one feature as about 13 short threads, each doing one
  thing, in a note Amp later marked as written for an older model era [sizing-prac-34] (A).
- An ablation over 176 matched conditions and four models found that planning "shifts from
  accuracy support for weaker models to cost reduction for stronger models" (arXiv 2609.20804) (M).

No source measures agent-owned against person-owned decomposition directly, and in the Anthropic
harnesses no person reviewed the agent-written list. The strength rests on convergence across three
labs, two vendors and practitioners.

### F5. The right unit is model-relative, and it has been growing — moderate (VOLATILE)

- Sonnet 4.5 needed context resets; Opus 4.5 "largely removed" context anxiety; Opus 4.6 dropped
  the sprint decomposition Opus 4.5 needed and ran coherently for over two hours in one pass
  [sizing-trend-2 to sizing-trend-4, sizing-lab-7] (L). Anthropic: every harness component "encodes
  an assumption about what the model can't do", and those assumptions "go stale" [sizing-lab-9,
  sizing-trend-55] (L).
- Current guides: Fable 5 is "particularly effective at end-to-end work that takes a person hours,
  days, or weeks"; "Start at the top of your difficulty range" and let it scope the task
  [sizing-lab-25, sizing-lab-26] (L). Opus 5 "performs best when given the complete task
  specification up front and left to run" [sizing-trend-49] (L). Opus 5.5 claims multi-hour audits
  and migrations end to end with little oversight [sizing-lab-29] (L).
- Usage data: autonomous tool-call chains rose from 9.8 to 21.2 and human turns fell from 6.2 to 4.1
  per transcript, February to August 2025 [sizing-lab-31] (M, vendor); the 99.9th-percentile Claude
  Code turn nearly doubled, from under 25 to over 45 minutes, while the median stayed about 45
  seconds [sizing-lab-32] (M, vendor).
- Practitioners: Karpathy went from "small incremental chunks" (June 2025) to large "code actions"
  and "get the agents looping longer" (January 2026) [sizing-prac-11, sizing-prac-12] (A); Cole
  Murray dates spec-to-pull-request with little friction to about December 2025 [sizing-prac-7] (A).
  Amp's current docs dropped "Break very large tasks up into smaller sub-tasks" but still say "Use
  one thread per task" [sizing-lab-61] (L). Cognition found managers "trained on small-scoped
  delegation default to being overly prescriptive" [sizing-trend-16] (A).

### F6. Vendors that publish a size give two-sided bounds, in hours or outcomes — moderate (VOLATILE)

| Source | Too small | About right | Too large |
| --- | --- | --- | --- |
| Claude Code agent teams [sizing-lab-20, sizing-trend-14] (L) | "coordination overhead exceeds the benefit" | "a function, a test file, or a review"; 5–6 tasks per teammate | "work too long without check-ins, increasing risk of wasted effort" |
| Codex goals [sizing-lab-41] (L) | one prompt | "bigger than one prompt but smaller than an open-ended backlog"; runs for hours | an open-ended backlog; loose lists of unrelated work |
| OpenAI goals cookbook [sizing-lab-42] (L) | ordinary requests: fix a bug, add a test, a focused change | work whose next step depends on what is learned, bounded by a budget and evidence-based completion | — |
| Devin [sizing-lab-55, sizing-lab-56, sizing-lab-57] (L) | — | "three hours or less" of the user's time per session; 4–8 junior-engineer hours per task (67% merge rate reported for 2025) | sessions over 10 ACUs flagged unhealthy: significant issues, or scope too broad |
| Factory Missions [sizing-lab-59, sizing-prac-33] (L) | a few straightforward features: use a normal session | about 1–500 features, a clear outcome, meaningful milestones ("a planning heuristic, not a hard limit") | over 500 features: split into Missions |
| Claude Code best practices [sizing-lab-14] (L) | "If you could describe the diff in one sentence, skip the plan" | — | — |
| Opus 5 guide [sizing-lab-23, sizing-trend-50] (L) | "Do not delegate work you can finish yourself in a handful of tool calls" | "genuinely independent, sizeable tracks" | — |
| OpenAI subagents (L) | do not decompose a single ordered chain of reasoning, shared mutable writes, or one slow external operation | read-heavy parallel work (exploration, tests, triage, summaries) [sizing-lab-40] | write-heavy parallel work: conflicts and coordination overhead [sizing-lab-40] |
| Augment (L) | — | 5–15 minutes per step | — |
| DORA [sizing-review-28] (P) | — | work items done in hours to a couple of days | over a week to finish and check |

The two-sided rules name the same forces: a floor set by coordination and fixed cost, a ceiling
set by time without a check-in. None sets the floor by lines, files or tokens. The one-fresh-context
advice is about topic, not size: Anthropic ("`/clear` between unrelated tasks"; a clean session with
a better prompt beats a long one with corrections), OpenAI ("one chat per coherent unit of work;
fork only when the work truly branches"), Cursor, Amp, Warp and Cognition all name a change of topic
as the boundary. `/clear` is free where `/compact` is itself a large request (Claude Code docs
[as-of 2026-09-22]). A brief, where the sources describe one, has four parts: goal, context, constraints
that must not change, and completion criteria with the command that proves them (OpenAI best
practices; Claude Code `/goal`: one measurable end state, a stated check, constraints, judged by a
fresh model).

### F7. The person's attention is the binding constraint, and per-unit touches spend it — moderate

- **Named scarcity.** "The only fundamentally scarce thing is the synchronous human attention of my
  team" (Lopopolo, OpenAI) [sizing-prac-28] (A); at 5–10 pull requests per engineer per day,
  switching was "very taxing" [sizing-prac-27] (A). Stripe: developer attention is among its most
  constrained resources [sizing-prac-23] (A). Cognition: heavy users become "bottlenecked on … the
  management, planning, and reviewing" [sizing-prac-3] (A). Willison can review and land "one
  significant change at a time" [sizing-prac-9] (A); Yegge sustains the pace a few hours a day
  [sizing-prac-22] (A); Ronacher: review is a queue whose input outgrows throughput
  [sizing-prac-39] (A), and when a harness judges "done", the person's review point disappears
  (lucumr.pocoo.org, 2026-06-23); Hashimoto has one background agent running 10–20% of his day and
  names his own supply of delegable work as "part of the challenge" [sizing-prac-16] (A); Kent Beck
  ended up "managing" the swarm himself [sizing-prac-17] (A).
- **Measured review load.** High-AI-adoption teams merge 98% more pull requests while review time
  rises 91% and pull-request size 154% (Faros, 10,000+ developers) [sizing-review-25] (M, vendor).
  Agentic pull requests wait 17.6 hours for pickup against 3.4 unassisted and merge within 30 days
  32.7% of the time against 84.4% (LinearB, 8.1M pull requests in 4,800 organisations)
  [sizing-review-12] (M, vendor). Anthropic: output per engineer up 200%, review "has become a
  bottleneck" [sizing-review-24] (L). Of rejected agent pull requests, 38% were abandoned without
  meaningful reviewer engagement [sizing-review-15] (M).
- **Approvals decay.** Users approved about 93% of Claude Code permission prompts, and attention per
  prompt falls as prompts multiply [anthropic-17] (M, vendor). Experienced users move from
  per-action approval to monitoring: auto-approve rises from about 20% to over 40% of sessions and
  interrupts from 5% to 9% of turns; Anthropic concludes that requiring approval of every action
  "will create friction without necessarily producing safety benefits" [sizing-lab-33,
  sizing-trend-28] (M, vendor). A persuasive explanation raises acceptance whatever its merit: in a
  study of people deciding with an AI's recommendations, explanations "increased the chance that
  humans will accept the AI's recommendation, regardless of its correctness" (Bansal et al., CHI
  2021, arXiv 2006.14779 [as-of 2026-10-01]) (M). No source was found for the claim that a review
  queue is read with less care the longer it grows; it is UNVERIFIED.
- **Stops pull earlier stops.** OpenAI: "A requirement to stop for review after the first
  implementation will pull the model toward an earlier stopping point" [openai-13] (L). A ticket
  boundary is such a required stop.
- **Where people want to be asked.** 11 of 21 experienced agent users preferred check-ins at key
  milestones and 2 only on risky events; they did not want constant interruption; a checkpointing
  harness caught all four oracle-required interventions where an unmodified coding agent caught
  half [sizing-trend-26] (M, n=21). In practice oversight is opportunistic, not scheduled (arXiv
  2606.05391) (M). Anthropic's Fable 5 guide: pause "only when the work genuinely requires them: a
  destructive or irreversible action, a real scope change, or input that only they can provide"
  [sizing-lab-27] (L). A forecast: agent products will ship a "human attention policy surface"
  within a year [sizing-prac-40] (F).
- **Some drop trackers entirely.** Steinberger tried Linear and other trackers and "nothing did
  stick"; "usually I'm the bottleneck" [sizing-prac-38] (A). OpenAI's Symphony reduces the person's
  review to merge or rework, with rework restarting from scratch [sizing-prac-27] (A).

No source measures the minutes a person spends per ticket. That per-ticket acceptance, sequencing
and closing scale with ticket count, and so with slicing granularity, is an inference from the
above and from one ledger's counts (§3); as a measurement of time it is UNVERIFIED.

### F8. Review needs bounded diffs, but a reviewable diff need not be a ticket — moderate

- **Size and effectiveness.** SmartBear/Cisco (2,500 reviews, 2006, vendor): found-defect density
  is highest under about 200 lines and falls above it; reviewers under 400 lines per hour find more
  [sizing-review-1, sizing-review-2] (M). The study assumes true defect density is constant across
  sizes, which its author says current literature "generally supports", and did not measure escaped
  defects [sizing-review-3]; the "70–90% defect discovery" figure is on SmartBear's marketing page,
  not in the study [sizing-review-4] (L). Google: about 100 lines is usually reasonable, 1,000
  usually too large; first feedback within an hour for small changes and about 5 hours for very
  large ones [sizing-review-5, sizing-review-8] (M, P). Microsoft: more files, a smaller share of
  useful comments [sizing-review-7] (M). Smaller changes are reviewed more effectively (Baum,
  Schneider, Bacchelli, EMSE 2019), and understanding the change is the key aspect of review
  (Bacchelli and Bird, ICSE 2013) (M). For one LLM reviewer (Claude Haiku 4.5), F1 fell from 0.657
  on diffs under 10 lines to 0.043 over 150 lines [sizing-review-22] (M, 150 samples, small
  buckets).
- **A floor, too.** Graphite: under about 25 lines the revert rate rises and total code shipped
  falls [sizing-review-11] (M, vendor, 2023). Google: a change must not be "so small that its
  implications are difficult to understand" [sizing-review-9] (P).
- **Agent pull requests.** Not-merged agent pull requests are larger, a small-to-medium effect;
  rejected ones touch more files [sizing-review-14] (M, 33,596 agent pull requests); submitter
  attributes, not size, dominate merge outcomes [sizing-review-18] (M); only 35.7% of rejections are
  clear agent failures [sizing-review-17] (M). LinearB puts agentic pull requests at 293 lines at
  p75, about 1.9x unassisted [sizing-review-13] (M, vendor). Cursor reports its long-running agents
  produced "substantially larger PRs with merge rates comparable to other agents" [sizing-lab-52]
  (M, vendor, no n or method).
- **The landing unit is cheap to cut.** "Several small PRs beats one big one, and splitting code
  into separate commits" is cheap because the agent does the git work [sizing-prac-10] (A). DORA
  warns against massive agent pull requests, since machine-generated code may cost more attention
  per line [sizing-review-28] (P).
- **Reviewers act on what they are asked.** Across 80,000 pull requests, stating the type of
  feedback needed went with 64–72% higher merge odds (arXiv 2602.14611, correlational) (M).

A reviewable landing unit is a few hundred lines at most; it can be a commit or a stacked pull
request within one ticket, landed as the implementer's milestones complete. What a second reader
finds, when a reviewer of another model family adds signal, and how many review rounds a large spec
takes are in [review.md](review.md).

### F9. Splitting one outcome across parallel writers costs reliability and tokens — strong

- Two agents each building one of two compatible features succeed about 30% less often than one
  agent building both [sizing-review-37] (M). Pre-write locking recovers reliability only by
  serializing 96.7% of runs [sizing-review-38] (M). Multi-agent frameworks fail 41–86.7% of the
  time, with gains over single agents often minimal [sizing-review-36] (M, 2025 models). Concurrent
  agent pull requests from different agents conflict 41.7% of the time against 19.8% from the same
  agent [sizing-review-21] (M). Multi-agent gains run from +80.8% on decomposable work to −70.0% on
  sequential planning; decomposability, not agent count, predicts the gain [sizing-review-39] (M).
  Across two benchmarks, raising the cap from four to six agents "tends to" lower scores, not
  monotonically, while input tokens rise (2,745M to 6,312M on one); recursion depth 3 scored below
  depth 1 in every reported row; decomposition helped long-horizon work with sparse dependencies,
  and single agents won on tightly coupled sequential work [sizing-review-40] (M). In a non-coding
  task over 4,400 pre-registered runs, intermediate partitions scored 0.830 against 0.720 and 0.770
  at the ends, short of the authors' pre-stated bar, a budget-matched single agent was within noise
  of the leader, and one plausible wrong intermediate record hurt the most fragmented configurations
  most [sizing-review-41] (M). Most published coordination gains sit below a local noise floor of
  about 15 points, the upper confidence bound of gaps between equivalent configurations
  [sizing-review-43] (M, one model, one benchmark). In Anthropic's multi-agent research system,
  token usage by itself explained 80% of the performance variance on its browsing evaluation
  (BrowseComp), with tool calls and model choice the other two of three factors explaining 95%, so
  test a single agent with the same token budget before crediting the extra agents (M, vendor,
  2025-06-13 [as-of 2026-10-01]). MAST (arXiv 2503.13657, more than 1,600 annotated traces from seven
  frameworks) sorts multi-agent failures into 14 modes under system design and specification,
  inter-agent misalignment, and task verification including premature termination; improving the
  agents' role specifications alone raised one framework's success rate by 9.4 points with the same
  model and prompt, and the authors conjecture that better base models will not remove these
  failures (M; the conjecture is theirs) [as-of 2026-10-01].
- Anthropic: agents use about 4x the tokens of chat and multi-agent systems about 15x; most coding
  has fewer truly parallelizable parts than research [sizing-lab-11, sizing-lab-12] (M, L). The
  Opus 5 guide claims Opus 5 "coordinates teams of subagents well" [sizing-lab-24] (L), a claim no
  independent source tests.
- Cognition: "Actions carry implicit decisions, and conflicting decisions carry bad results"
  [sizing-prac-1]; ten months on, what works keeps "writes … single-threaded", and further agents
  contribute intelligence, not actions [sizing-prac-2] (A). Cursor: flat self-coordination slowed 20
  agents to the throughput of 2–3, and agents "made small, safe changes instead" of owning hard
  problems; locks failed, and a planner, workers and a judge with periodic fresh starts held up
  [sizing-lab-50] (A). Yegge: swarming creates a merge-queue problem [sizing-prac-21] (A).
- Parallelism paid where the pieces were independent and checkable: 16 agents made progress while
  there were many independent failing tests and collided on "one giant task" until a GCC oracle
  split the kernel build into per-file pieces; the author says the task verifier must be "nearly
  perfect" [sizing-lab-36, sizing-trend-7, sizing-trend-8] (A); Airbnb cut a test migration of about
  3,500 files into per-file steps with retries, migrating 75% in the first four-hour run and the
  whole in six weeks [sizing-trend-33] (A).
- Claude Code agent teams name two failure modes of a shared task list: a task never marked
  complete blocks its dependents, and a lead decides the team is finished early (docs
  [as-of 2026-09-20]) (L).

### F10. Charting far ahead bakes guesses in; a living plan revises them — moderate

- A pre-charted decomposition cost 80.5% more tokens than a monolithic run when a step failed,
  because the failure re-ran everything downstream; re-running only the failed piece cost up to
  51.7% less than monolithic in one workload and about 35% less in the other [sizing-review-42] (M,
  two workloads, small token counts).
- An early wrong decision survived 27 compactions [sizing-trend-23] (M, one run). Devin "performs
  worse when you keep telling it more after it starts" [sizing-lab-58] (L). Huntley throws the plan
  out often [sizing-prac-19] (A); Cursor's planners restart cycles fresh [sizing-trend-11] (A). A
  way-finding map of 27 tickets charted up front was stale by the thirteenth ticket, by its author's
  own record (Matt Pocock's `wayfinder`, 2026-08) (A).
- No measured comparison of a dependency-graph backlog with a flat ordered list was found; the
  Ralph loop's deliberate absence of a graph is the live counter-position (A).

### F11. Every unit has a fixed cost, which sets a floor — moderate

- Reading and searching take 56.2% of tool turns and 46.5% of tokens in 300 GPT-5.4 trajectories on
  SWE-bench Multilingual; the median run makes 15.5 exploration calls before its first edit, and
  the first edit comes at turn 8.47 on average over 284 trajectories; unresolved runs explore more
  (8.3 against 6.7 turns), so excess exploration is a failure signal, not warm-up [sizing-check-1]
  (M). Each fresh unit pays this again.
- Batch-size economics: total cost is a U-curve of per-batch transaction cost against holding
  cost, with a flat bottom (a 10% sizing error costs 2–3%); where each batch carries a high fixed
  overhead, larger batches win, and the lever is to cut the overhead [sizing-review-29,
  sizing-review-30] (P, secondary account of Reinertsen).
- In one ticket ledger (§3), implementing a ticket cost 79k–530k tokens, reviewing it 67k–152k, and
  a three-line docstring about 136k to implement and 125k to repair because the harness re-read the
  repository (O). The fixed per-ticket costs (warm-up, reviewer, acceptance, confirmation) do not
  shrink with the change.

The small-batch argument assumes the transaction cost is low. For agent work the transaction cost
that remains is mostly the person's: accepting, sequencing and confirming. Lowering it (fewer
acceptance units, machine-checked closing) moves the optimum smaller again [sizing-review-45] (A);
holding it fixed while cutting finer moves the total cost up.

### F12. What genuinely pushes a task smaller — moderate to strong, by force

| Force | Evidence | Where it applies |
| --- | --- | --- |
| Irreversible or shared-system action | Unguided, Opus 4.6 "may take actions that are difficult to reverse" [sizing-trend-29]; pause for "a destructive or irreversible action" [sizing-lab-27] (L) | A person's decision before the edge; a ticket boundary where the edge is |
| Reliability where failure is costly | p80 4–10x shorter than p50 [sizing-horizon-8]; 98%+ needed for critical work [sizing-horizon-11] (M, L) | Shorter execution units and stronger checks for critical work |
| Spread of one pass | Success falls with files and lines [sizing-horizon-27 to sizing-horizon-30] (M) | The execution unit; a milestone per neighbourhood of the code |
| Context and compaction | Ran out of context mid-feature [sizing-lab-1]; one change per prompt [sizing-prac-24]; compaction loses decisions [sizing-trend-18] (L, A) | The execution unit, and more for weaker models |
| Reviewability | F8 (M) | The landing unit: commits and pull requests |
| Parallel wall-clock | Independent per-file or per-test work with a verifier [sizing-trend-33, sizing-lab-36] (A) | Separate tickets only with disjoint paths and their own checks |
| Weaker or cheaper implementer | One feature at a time was "critical" for Opus 4.5 [sizing-lab-3]; Devin's three-hour rule [sizing-lab-55]; "narrow it down" when it goes off the rails [sizing-prac-18] (L, A) | The execution unit inside the plan; the ticket only when the implementer cannot plan |
| Intent not yet settled | Mid-task requirement changes hurt [sizing-lab-58]; plan approval up front because a wrong assumption compounds [sizing-lab-53] (L) | Settle intent before the work; a question is its own unit, not a slice |
| Failure retry cost | Restarts are expensive, resume instead [sizing-trend-13]; retry only the failed piece [sizing-review-42] (L, M) | Checkpointed, resumable execution units |
| Too long without a check-in | "increasing risk of wasted effort" [sizing-lab-20]; Cursor: agents "occasionally run for far too long" [sizing-trend-11] (L, A) | Milestone readings, not per-step tickets |

Every force in this table is real. Only three (the irreversible edge, a parallel stream on
disjoint paths, and an unsettled intent) call for a separate acceptance unit; the rest are served
by a smaller execution or landing unit inside one ticket.

### F13. Trend: the unit keeps growing, and its reliable core grows more slowly — forecast (VOLATILE)

- METR: if the trend holds, agents will carry out month-long projects by the end of the decade
  [sizing-trend-35] (F); the measured doubling is now 89–131 days [sizing-trend-36] (M), its
  extension a forecast.
- Anthropic's 2026 trends report: agents working "for days at a time … with minimal human
  intervention focused on providing strategic oversight at key decision points" [sizing-lab-34]
  (F). Anthropic's harness post expects models to work longer on harder tasks, and with each new
  model to strip pieces no longer load-bearing and add new ones [sizing-trend-55] (F). In Anthropic's
  December 2025 internal study, more than half of engineers said they can fully delegate only
  0–20% of their work [sizing-lab-30] (M, vendor).
- Against: the p80 horizon trails the p50 by 4–10x [sizing-horizon-8]; METR's suite saturates above
  16 hours and Opus 5.5 was "an incremental improvement … rather than a discontinuous jump"
  [sizing-horizon-9, sizing-horizon-17] (M); the headline many-agent demos "all share a property
  most real software doesn't: a simple, verifiable success criterion" [sizing-prac-5] (A); Epoch
  found long work held "When AI is working to a detailed, checkable specification"
  [sizing-trend-51] (M, one project); a codebase run without review for about two weeks decays, by
  Cognition's experiments at the state of the art of December 2025 [latent-space-19] (A).

## 3. What per-ticket process costs, measured in one ticket ledger

These counts come from one repository's own tickets: 165 issues over five days, implemented by
agents (a smaller model as a subagent, or a larger orchestrating session), reviewed by a
fresh-context reviewer, and accepted by one person. Every tracker event ran under the person's
one account, so the person's own acts are counted from the words quoted in relayed records and
acceptance comments, not from the tracker. Minutes are not measured.

**Fixed cost per ticket.** Eleven tickets implemented from a compiled brief and reviewed by a
reviewer that wrote neither brief nor code:

| Measure | Value |
| --- | --- |
| Implementing tokens per ticket | 79k on the smallest first pass to 530k after two repair rounds; briefs of 95–101 lines cost 79k–145k, briefs of 415–488 lines 197k–530k |
| Reviewing tokens per ticket | 67k to 152k |
| Drafting tokens | about 491k for eight drafts across four rounds, not decomposed per ticket; the drafter's reading found sixteen gaps in the spec, one a real defect |
| A three-line docstring | about 136k to implement and 125k to repair: the harness re-read the repository |
| First-pass checks | every named check PASS on nine of nine tickets in the second batch |
| Reviewer verdicts | nine of nine accepted "with fixes" (2 to 6 fixes each); none clean, none rejected |
| Most frequent reviewer finding | a test that stays green with the behaviour broken, on every ticket but one; then a brief naming the wrong fixture, file or precedent (4); an instruction read as leave to do less (1); wording a model could misread (3); an edge-case row with no test (4) |

A smaller model built every slice from the compiled brief and the repository alone, across two
vendors and two harnesses: the first two runs were Claude Sonnet 5 as a subagent (a 149-line brief;
about 93k tokens to implement and 17k to repair) and GPT-5.6 Luna at maximum effort through `codex
exec` in a workspace-write sandbox (171 lines; about 136k and 125k), and the later ones the same
smaller model as a subagent. One run stopped on its brief's stop condition and needed a person's
decision, which became a ticket of its own before the work resumed; another met a named check
failing for a change outside its bounds, withheld its commit and said why. A ticket that asked for a
failing check first got none, because the instruction for recording one lived in a skill the run was
not given. Every reviewed slice needed at least one repair that a fresh reviewer found. There is no
baseline of the same slices without a brief, so nothing here shows the brief saves anything. The
same pattern held for eighteen larger work packages built by a larger model from hand-written briefs
of 1,400–2,900 words: implementing took 186k–411k tokens, fix rounds 12k–174k and reviews 149k–252k;
17 of 18 fresh-context reviews returned "fix", and every package had at least one fix round. It held
again for 26 packages built from briefs that pointed into a plan reviewed to GO: 22 went back for at
least one fix round ([review.md](review.md) §4).

**Grain against diff.** A later batch of 35 tickets, every one a finding discovered during earlier
work, had a median diff of 45 lines (21 to 294) and a median brief of 73 lines; on 25 of the 31
that landed, the brief was longer than the whole diff (smallest ratios: a 55-line brief for a
21-line diff, 60 for 22, 68 for 22). Two tickets carried the same fact in two files; four were
`--help` wording fixes of 22–52 lines each. The orchestrator executed the 31 landed tickets as 6
group worktrees, so the grain was re-merged at execution time and the tickets remained as
bookkeeping. An earlier batch, first cut as 41 drafts "one per fix" (16 of them one-line changes,
five inventing separate claim names for one test file), was regrouped into 8 tickets plus one
housekeeping commit for the one-line changes. How the findings deferred during review fared when
they were triaged against the source is in [review.md](review.md) §5.

**Split rules without merge rules.** The rules that produced these batches carried four concrete
split triggers (few files, one neighbourhood, a shared module or irreversible edge on its own, a
change a reviewer cannot read in one sitting is two tickets), plus "a design that must decide which
change lands first is two tickets", "cut at a dependency-layer boundary", and "where the axis rule
meets the ceiling, the ceiling wins". The merge side held one abstract rule ("nothing smaller"),
one one-sentence floor, and a feedback trigger that depended on an implementer volunteering that a
brief was unneeded. That trigger fired in 0 of 136 closing notes, although 17 tickets closed with
"decided beyond the brief: none" and "surprises: none" on diffs of 22–145 lines. The floor governed
up-front slicing only: a rule that a finding not fixed in place becomes its own ticket let every
later one-liner through. Writing each brief for the least capable implementer made every brief long,
and the ceiling then read brief length as a split signal, so the more thorough the brief, the more
the rules suggested splitting. Specs that fixed grain themselves ("one ticket per surface", "one
triage ticket per package") overrode the slicing rules; one produced 25 triage tickets each carrying
a person's confirmation.

**The person's acts.**

| Act | Count in the window | A judgment only the person makes? |
| --- | --- | --- |
| Read and approve a breakdown | a few real readings, after which a standing word replaced the reading and later breakdowns were published unread | yes |
| Accept each ticket (apply the label) | one labelling per ticket at creation, and again after an edit; 77 of 174 labellings carry a comment recording acceptance on the person's word | no, per ticket; the judgment is the breakdown reading |
| Re-accept after an edit | each within seconds of the edit (a later count found 22 of 23 putting the label back 2–6 s after removing it); 4 of 9 driven by a decision that dictated the edit | the decision was the judgment, the relabel was typing |
| Confirm a per-ticket `human:` claim | 77 claims on 71 tickets; 79 records from about 14 distinct replies, the largest of which became 36 records on 18 tickets | about 18–23 of 77 |
| Hold a ticket that is itself a person's act (tag a release, create labels, commit an authorization record) | 9 tickets | the act yes, the ticket around it no |
| Read an end-of-run list | one list of about 23 items, about 11 of which asked for nothing | part |
| Answer a question asked twice | about 6 | no |

The decision record kept beside the ledger numbered 124 decisions put to the person over six days
(the five days of ticket creation and the day after), several of them prose that no command drew.
Setting up the tracker store took four of the person's acts (the store-and-labels decision, creating
the labels, writing the declaration, committing the write grant), of which only the first was a
judgment (O).

The 77 confirmations by what they asked: 25 "triage recorded" (a lint of the triage file would
settle each), 11 naming an agent or reviewer as the actor, 7 observations of external state a
command reads (`gh run view`, `git ls-remote --tags`, `gh label list`, a release checker's version
row), 11 audit tables accepted unread, 14 wording readings, 4 decisions or loosenings only the
person makes, 3 parent roll-ups and 2 report-field checks. Of the tickets left open at the end, 8 of
10 waited on a person or on nothing: a confirmation an agent had already observed, a floor re-apply,
a ticket whose only blocker had been dropped, or an acceptance that lapsed on the agent's own edit
after its work had landed. Every standing authorization for recurring acts lived in memory and
comments, not in a record the next session read, so it was restated per session.

## 4. What slicing experiments showed

**One spec, many cuts.** One spec for rewriting a project's model-facing text, with its checks,
generated facts and measurement runs, was sliced through its first release by the same slicing method
under different split rules, each by one fresh run that read the spec, the repository and its closed
tickets; the implementer was assumed to be an agent of the slicer's own model, taking tickets one at
a time. Runs used GPT-6 Sol at high effort through Codex, Claude Opus at high effort, and a Claude
orchestrating session.

| Split rules in force | Tickets |
| --- | --- |
| Unit = what one implementer completes in one fresh context from the brief, written for the least capable implementer; four ceiling triggers; one test seam per ticket | 54 (1 parent, 53 children; about 330 agent-hours) |
| Four boundaries (irreversible edge, a decision the person must make first, parallel work on disjoint paths, work beyond one reliable run), with large work cut at checkable end states | 25 and 27 |
| The same, with a size bar of about twice the largest ticket that landed clean | 14, 22 and 27 |
| Split only at an edge, a decision between, parallel work on disjoint paths, or a recorded failure of this implementer at that size | 5 and 7 |

An earlier estimate under the first rules, made before any run, was 50–55 tickets; a person judged
a right-sized breakdown at about 11. The runs under the last rules produced two very large tickets
(roughly 120–160 and 70–90 agent-hours), to be reviewed milestone by milestone and shrunk only if
the record later shows one stalling. Where runs named what they folded: small surfaces merged into
neighbours whose brief would otherwise outweigh them; text that must agree (a contract, the skill
that restates it, the template that renders it) merged across layers; a format and its reader
merged; per-surface and per-family lists in the spec became an order of work inside tickets; and
one-sentence changes became commits. Scope: one spec, one run per configuration; nothing about how
the resulting tickets would have landed.

The size bar in the third row reads the ledger's record of the largest ticket each implementer had
landed clean: 3,960 lines over 3 files for a Claude Code subagent on Sonnet 5 (11 clean tickets),
955 lines over 16 files for an orchestrating session (70), and 47 lines over 2 files for GPT-5.6
Luna at maximum effort through `codex exec` (1) (O, the ledger's audit).

**A model judge of the cuts.** gpt-6-astra at high effort, told neither the slicer nor the rules
behind each, read four of these breakdowns beside this reference's sizing evidence. It
ranked the 22-ticket cut first, then 27, 14 and 54; called 18–22 tickets right-sized for the first
release and 22–28 for both; found the 27-ticket cut's size arguments at odds with its own estimates
(a merge said to exceed a 1,900-line bar summed to 3,400 lines); and judged the 14-ticket cut to
assume 30–45-hour runs that no evidence supports. A person had judged about 11 right-sized, and the
last rules gave 5 and 7. One judge and one run, its agreement with a person not
measured: a reading, not a measurement (A).

**With and without a slicing guide.** On a small fixture spec whose work is one outcome, three of
three runs without a slicing guide cut it into two tickets along a module line (command line and
renderer) and none wrote the ticket block a tracker reader parses; with the guide, one ticket each
time (one model, three runs per arm). Method and the rest of those runs:
[evaluations.md](evaluations.md).

**Rule forms that over-slice.** Read against these results and F1–F12, each of these rule forms
pushes toward more tickets than the outcome needs:

| Rule form | Why it over-slices |
| --- | --- |
| "A ticket is what one implementer completes in one fresh context" | Defines the acceptance unit by the execution unit; labs run many contexts per handed-over task behind an agent-owned plan (F4) |
| "A change a reviewer cannot read in one sitting is two tickets" | Reviewability is a landing-unit property, met by commits or stacked pull requests inside one ticket (F8) |
| "A design that must decide which of its changes lands first is two tickets" | Ordering inside one outcome is a milestone plan's job (F4, P7); a boundary adds an acceptance and a required stop [openai-13] |
| "Write for the least capable implementer expected" as the size reference | Shrinks every ticket for every reader; the evidence puts that adjustment in the execution unit (P9) |
| "The person accepts each ticket" | Scales the person's work with granularity; the evidence favours acceptance at the breakdown, the milestones and the edges (F7, P5) |
| "A finding not fixed in place becomes a ticket" | Lets discovered one-liners past the floor (§3) |
| A spec that says "one ticket per surface" or "per family" | Fixes grain outside the slicing rules; treat it as an order of work |
| A numeric bar of words or lines per ticket | Makes length, not outcome, the boundary |
| Process tiers set by lines changed | Diff size is not risk: by one gate's rules (50 lines or fewer small, more medium, a listed path large), a 49-line authorization change outside the listed paths was small and a 51-line documentation rewrite medium; the bar rewarded splitting commits and never ran the check the risk needed (A, an audit of one repository's process gate) |

Rules consistent with the evidence: a floor on one-sentence changes, a flat parent with independent
children on disjoint paths, slicing on the seam that proves the change rather than on the list of
findings or modules, and charting to the next milestone and no further.

## 5. Writing tickets a person reads and a smaller model builds from

**The detail is what the model runs on.** On SWE-Bench Pro with two open models, removing an
issue's interface section (signatures) cut solve@3 by 33–40 points and its requirements section by
55–65; removing section headers cost 10–30 and flattening lists 11–27, with no content removed
(arXiv 2607.07593, 2026-07) (M). In the same paper's observational study (433 issues × 87 agents,
difficulty controlled), one standard deviation more log-length went with 51% lower odds of
resolution; that is correlational. Context files that add length raised inference work by more
than 20% with no gain in success (arXiv 2602.11988) (M).

**What a smaller implementer needs.** In one ticket ledger, a smaller model was run read-only to
plan two tickets without editing, before and after their briefs were rewritten to give every symbol
with its shape, verbatim text to be written, real command output, fixture shapes, and each test
named by what it fails under. It listed the symbols it would touch, the guesses where a wrong guess
makes a wrong change, and contradictions with the code. Wrong-change guesses went from 5 (two
critical) to 0 high and 1 medium on one ticket and from 4 to 1 on the other; contradictions with the
code from 1 to 0; the code it had to open fell from most of the symbols (9 of 21 on one ticket) to
locations only. Its self-rated confidence barely moved (6 to 6, 6 to 7) and is not evidence (O, two
tickets). The rewrite grew tickets from about 150 lines to 230–385 lines (about 2,000–2,500 words,
the largest regrouped drafts about 5,400), which the person accepting them found harder to read.
Reviewers of implemented briefs most often found: a test that stays green with the behaviour broken,
a named fixture or precedent that was wrong, an instruction read as leave to do less ("restates none
of that", read as leave to drop a value silently), wording a model could misread, and an edge-case
row with no test (§3). Briefs also lacked, in reviewers' words: an assertion elsewhere in the file
that the change necessarily breaks; whether prose, not only assertions, was to be reconciled; a type
imported from a module that must import this one; a method named without its failure semantics;
silence on byte-order marks, CRLF, duplicates and empty items; a worked example that proved nothing;
a named mutation control that did not bite; an edge-case table that never said each row must call
the real reader, so rows asserted source text ([testing.md](testing.md) §1); and a claim wider than
the work. Seven briefs failed the same way: they named tests their bounds excluded, pointed at a
document the target does not hold, left a shared table unsaid so three surfaces re-spelled it
locally, or put a maintenance note into shipped text. Rules that follow: bounds carry every file the
named tests live in, and a pointer names a document the reader can reach.

**How long tickets ran.** Across 192 tickets in one repository's tracker, the
median body was 10,714 characters, with quartiles of about 3,700 and 18,500 and the largest 53,490;
none reached GitHub's 65,536-character cap. The median was about 2,800 characters over the first 50
tickets, about 18,900 over the next 50 and about 11,000 after (O).

**Linting a ticket does not check it against the code.** Rewriters who opened every pointer in eight
drafts that already passed the ticket lint found more than forty statements the tree contradicted
(O, one batch). Every run also needed procedural help the brief did not carry (the worktree path,
the `PATH` line, what not to run, the commit convention), which a workflow document or skill loaded
by the implementer supplies better than each brief. A spec written so that a smaller implementer
decides nothing drew a NO-GO from an adversarial reviewer in nine consecutive rounds before a GO
([review.md](review.md) §4).

**Brief sections that carry a decision.** Outcome (what becomes observably true, and for whom);
approach (the chosen approach and one line on the near alternative rejected, with an optional
suggested order); design (responsibilities, exact signatures, data structures, invariants, error
handling, traps in the existing code, and an existing file whose shape to follow); edge cases (a
table of scenario, expected result and the test proving the row); tests (the seam the tests drive,
then each test by name with one sentence on what it asserts); must not change (stated as behaviour,
not files); stop if; non-goals. Existing code is named by path and symbol, never by line number.
Leave out a restated spec contract, the slice's own implementation, guidance every ticket would
repeat, and task-list checkboxes. Everything is decided unless marked as a suggested order or a
hint.

**Two readers.** "A ticket has two readers: the person who accepts it, who reads its first lines,
and the implementer, who reads all of it. Write for the first without removing anything the second
needs." For the first reader: the outcome opens with one sentence, followed where there is more than
one change by a table of one row per change and the tests that prove it; an optional "Accepting this
decides: …" line where acceptance settles something only the person can see; each design bullet
opens with its part in bold and its decision in one sentence; one decision per sentence; one line
per rejected alternative; a worked example stated once, under a name; tables only for short cells,
and a column empty in every row dropped; a finding outside the bounds named by the ticket it became.
For the second: shapes copied unchanged from the tree go at the end of their section in one
collapsed block headed "Reference for the implementer (required)", which the implementer is told is
not optional because it is collapsed only on the tracker; real output the new code parses stays
beside the rule that reads it.

**Readers scan.** The same text written concise, scannable and objective measured 124% more usable
than the control (Morkes and Nielsen, NN/g, 1997, 51 users, web pages) (M); eyetracking finds
reading only headings and subheadings ("layer-cake") the most effective scanning pattern (NN/g,
2019) (M). Established practice: key point first and first words that carry information (NN/g
inverted pyramid; bottom line up front; Google Tech Writing, "Documents"; US plain-language
guidelines); explanation kept apart from reference, which "describes and only describes"
(Diátaxis); a guide-level section apart from a reference-level one (Rust RFC template); an overview
before details (Google design docs); progressive disclosure at most one level deep (NN/g); tables
for items with three or more short related fields, split when cells grow (Google developer style
guide) (P). No study was found of where a reference block should sit in a short task document for a
coding agent; position effects are measured at far larger inputs than a 6–16 thousand-token brief.

**Defects seen in hard-to-read tickets.** An outcome that narrates internals before the
consequence; a design that opens with a table of unchanged shapes before its first decision; single
bullets of 30–50 lines; table cells of 60–90 words; worked examples repeated two or three times; an
"on error" column empty in every one of 41 rows; the one question for the person placed last,
under the stop conditions; a finding outside the bounds left as a non-goal rather than drafted as
its own work (A, two tickets examined).

**A readable shape.** An outcome sentence stating what becomes true and for whom; a design stating
the decisions; tests named by the break each catches; limits with the condition to stop and ask;
and a machine-readable block with what it reads, its bounds and the checks that prove it done. Tickets
in this shape ran to about 200 words each.

**Stating a requirement so a check can be written.** Prior art (P) [as-of 2026-10-01]:

- EARS (Easy Approach to Requirements Syntax; Alistair Mavin and colleagues at Rolls-Royce, first
  published 2009) restricts a requirement to five sentence shapes, each naming the system and its
  response: ubiquitous ("The <system> shall <response>"), state-driven ("While <precondition>, the
  <system> shall …"), event-driven ("When <trigger>, …"), optional feature ("Where <feature is
  included>, …") and unwanted behaviour ("If <trigger>, then the <system> shall …"), with
  combinations of the keywords for complex cases ([EARS](https://alistairmavin.com/ears/)).
- Example Mapping (Matt Wynne, Cucumber, 2015) maps one story in about 25 minutes onto cards: the
  story, its rules, examples for each rule, and the questions nobody can answer yet, parked rather
  than guessed. "A table covered in red (question) cards tells us that we still have a lot to learn
  about this story", and one covered in rule cards that the story may need slicing
  ([Cucumber](https://cucumber.io/blog/bdd/example-mapping-introduction/)).
- A job story frames one outcome by its situation: "When <situation>, I want to <motivation>, so I
  can <expected outcome>" (Alan Klement, Intercom, 2013; read through secondary accounts).
- A non-functional requirement stated without a unit and a threshold cannot be checked, and a rule
  with its example becomes a Given/When/Then that names the check proving it.

Each maps onto the brief's edge-case table: a rule, its example, and the test that proves the row.

**On the tracker.** GitHub's collapsed `<details>` sections keep their full content in the export,
so the implementer's reference block reaches an agent that reads the body; whether a model weighs
collapsed content less is unmeasured. An issue body is capped at 65,536 characters, which a brief
quoting every cited section verbatim can exceed. Acceptance, confirmation, evidence records, the
GraphQL export, commit identity and rendering are in [ticket-tracking.md](ticket-tracking.md).

## 6. Ticket systems: prior art

The systems in the table as read [as-of 2026-09-23]:

| System | What it does that bears on ticket design |
| --- | --- |
| Matt Pocock's skills, `wayfinder` (MIT; changed 2026-08-19) | For work that spans sessions with an unclear route: one map issue (destination, notes, decisions so far, not yet specified, out of scope) and child tickets that are questions (research, prototype, grilling, task), each sized to one session. The frontier is the open, unblocked, unclaimed children, in the tracker's native sub-issues and blocking relations; one ticket resolved per session, the answer a closing comment; work that cannot yet be phrased waits in the map. It plans and never builds and is invoked only by the user. Its author records its gaps: no hard stop, no way to revise a wrong decision, and a 27-ticket map stale by the thirteenth. Also: tracer-bullet slices, blocking edges, a quiz before publishing, tracker indirection (v1.2.3) |
| BMAD 6.12 and its ticketing preview | Frozen person-owned intent; thin tickets; `covers` links to requirements; `hitl` marks |
| OpenSpec 1.13 | A named-message validation contract; no task-to-requirement link and no evidence model |
| Doorstop, OpenFastTrace | Suspect links when a linked item changes; revision in the id |
| HumanLayer commands | Manual verification an agent may not tick |
| CCPM | The cost of keeping files and issues in sync |
| Gerrit Change-Id, Jujutsu change ids, GitHub and GitLab merge methods | Identity that survives a rebase or squash, which a commit hash does not |
| Beads | `discovered-from` for work found mid-flight |
| Spec Kit, Epiq, git-bug; GitHub issue dependencies and sub-issues, `gh` 2.101.0 | Tracker-native relations and spec-driven templates |
| Claude Code agent teams | A shared task list with dependencies (F9 names its failure modes) |

From this reading: a dependency cycle is an error; a ready frontier must tell a finished frontier
from a blocked one; a ticket with open children is never ready; and schedulers, rankings, locks,
budgets and retry counts inside the ticket engine were judged unnecessary.

**Independent results on visible checks.** Agents saturate a visible test suite while a held-out one
lags, and the gap grows with code size (arXiv 2605.21384, 2026-05-20) (M); with a hidden oracle in
the loop, scores approached perfection while the library stayed dead or absent (arXiv 2606.28430,
2026-06-26) (M). A ticket's own checks are therefore evidence of the ticket's claims, not of the
outcome.

**Practitioner positions.** Ralph loops: one task per iteration, fresh context each time, state in
git and files, a person's Ctrl-C between tasks (ghuntley.com/loop, 2026-01) (A). Ball: verify rather
than read, and scale review depth to blast radius (2026-01) (A). Hashimoto: an agent's own success
signal saturates, and scope is the bumper (A). Willison: a narrow first prompt, widened on success
(A). On spec-driven work, Hacker News: "a detailed-enough spec is just code you can't run"; the
counter is that specs earn their keep only where plan-and-code fails (A).

## 7. Contested

**"Small incremental steps" against "hand over the whole outcome."** On one side: Karpathy in 2025
[sizing-prac-11], Harper Reed [sizing-prac-13], Osmani [sizing-prac-14], Hashimoto
[sizing-prac-15], Spotify [sizing-prac-24], Amp [sizing-prac-34], Devin's three hours
[sizing-lab-55], GitHub's "clear, well-scoped" issues [sizing-prac-35]. On the other: Fable 5 and
Opus 5 guidance [sizing-lab-25, sizing-trend-49], Cursor's long-running agents [sizing-lab-52],
Factory Missions [sizing-prac-31], OpenAI's 25-hour run [sizing-lab-43], Karpathy in 2026
[sizing-prac-12]. The two sides mostly describe different units. The small-step advocates describe
the execution loop, often with a person pairing at each step; the outcome advocates describe the
acceptance unit, with small steps inside it that the agent cuts and checks. Both agree the steps
are small; they differ on who cuts them and who must accept each. Where they genuinely conflict is
weaker models and settings without a runnable check: there, the small-step side has the better
evidence (F1, F2, F3).

**Whether agents coordinate well now.** Anthropic says Opus 5 "coordinates teams of subagents well"
[sizing-lab-24] (L); every independent measurement of parallel writers (F9) points the other way,
though none tests Opus 5.

## 8. Figures often misquoted

| Figure as it circulates | What the source says |
| --- | --- |
| Stronger models succeed by matching the gold patch's file count, weaker ones by exceeding it (arXiv 2609.01271) | The difference is by model family: Claude matches the gold scope, Qwen exceeds it at every scale [sizing-horizon-31] |
| Agent pull requests are "2.6x larger at p75" (LinearB) | 2.6x is AI-assisted pull requests (408 against 157 lines); agentic ones are 293 lines at p75, about 1.9x [sizing-review-13] |
| "The top quartile runs 54% AI-assisted PRs but under 5% fully autonomous" (LinearB) | Not found on any LinearB page read; UNVERIFIED |
| "Across four agent benchmarks, four to six agents dropped scores" (arXiv 2609.19759) | Two benchmarks; more agents "tends to" lower scores, not monotonically [sizing-review-40] |
| "More pieces is an inverted U" (arXiv 2608.23395) | The authors call the intermediate-optimum hypothesis "unsupported at pilot scale"; a non-coding task [sizing-review-41] |
| Anthropic's harness "cost ~20x a solo run" after removing sprints | The 20x is the first harness (Opus 4.5, sprints, $200 over 6 hours against $9 solo); the harness without sprints ran Opus 4.6 for 3 h 50 min at $124.70 [sizing-lab-4, sizing-trend-4] |
| Anthropic's 2026 trends report: "0–20% fully delegated" | The 0–20% comes from Anthropic's December 2025 internal study: more than half of engineers say they can fully delegate only 0–20% of their work [sizing-lab-30] |
| Re-running only the failed subtask "cost 51.7% less than monolithic" (arXiv 2605.15425) | "Up to" 51.7%, in one of two workloads; about 35% in the other [sizing-review-42] |
| The median run makes 15.5 exploration calls "before its first edit, at turn 8.5" (arXiv 2606.14066) | 15.5 is the median; the first edit comes at turn 8.47 on average, over 284 trajectories [sizing-check-1] |
| "Removing the global plan costs 14.06% on coding tasks" (arXiv 2504.16563) | Legal tasks; the 14.06% is removing a coding skill |
| Multi-agent gains on SWE-bench Verified | Traced only to vendor pages |
| METR's late-2025 developer uplift figures | METR calls that experiment's data "an unreliable signal": developers who would not work without AI declined to take part, which "likely biases downwards" its speedup estimate, and the study's design is being changed (2026-02-24) [as-of 2026-10-01] |
| A plain-language memo is read 17–23% faster | Found only in secondary sources |
| A 35-word sentence limit for tickets | Opinion, not evidence |

## How to apply

1. Settle intent first. An open question is its own unit, put to the person before any cut.
2. Cut acceptance boundaries only at an irreversible or shared-system edge, a contract consumed
   outside the ticket, a decision the person must make first, or parallel work on disjoint paths
   with its own check (P5, P6).
3. Put everything else inside the ticket as milestones: each finishable in one loop, each with a
   validation command, a progress file the implementer keeps, progress claims checked against tool
   results, and a fresh-context verification at intervals on long work (P8).
4. Land reviewable commits or stacked pull requests of a few hundred lines as milestones complete;
   do not make each one a ticket (F8).
5. Apply the floor to discovered work too: a later one-sentence finding rides in an open ticket that
   touches the same files, or lands as a commit of its own (P3, P11).
6. Give every split rule a matching merge rule, and treat a spec's "one per X" as an order of work
   (P10, P11).
7. Ask the person for a confirmation only where no command could settle it and no single reading
   answers for many; a CI conclusion, a tag on the remote or a label list is a command's check
   (P12). Let one reading of the breakdown accept its tickets, and let an edit that changes no
   outcome, bound or check leave acceptance standing.
8. Write the ticket for two readers: the outcome and the person's question first, decisions next,
   tests named by the break they catch, stop conditions, then reference (P13).
9. Re-read the sizing at each model generation: shrink milestones for a weaker implementer before
   shrinking tickets, and merge tickets when closed ones show the split was not needed (P9).

## Limits and open questions

- No controlled comparison of ticket granularity exists: no source runs the same body of work cut
  coarse and cut fine and measures outcome quality and the person's time. Every claim about the
  person's time is guidance, telemetry of a different quantity (review latency, pull-request
  throughput, approval rates), anecdote, or counts from one ledger.
- Horizons measure clean, low-context tasks; the reliable unit in a repository the agent knows
  through its instruction files is unmeasured. METR published no horizon for Claude Opus 5.5.
- The newest long-run claims (25-hour, 38-hour and multi-day runs) are single runs reported by the
  vendor or its customers [sizing-lab-43, sizing-trend-47, sizing-prac-29].
- Several measured results are small or single-author: the Hedwig evaluation (2 tasks, 11
  operations) [sizing-trend-27], the checkpoint survey (21 people) [sizing-trend-26], the
  LLM-reviewer size result (150 samples) [sizing-review-22], the noise-floor paper (one model, one
  benchmark) [sizing-review-43]. Review-size studies predate agents (SmartBear/Cisco 2006, Google
  2018, Microsoft 2015, Graphite 2023) [sizing-review-1 to sizing-review-11].
- The ledger counts come from one repository, one person and five days of ticket creation (six for
  its decision record); the slicing experiments from one spec and one run per configuration.
- Open: what a ticket costs the person in minutes; whether an agent-owned plan drifts without
  milestone readings, and how often a person must read them; whether AI review holds on
  multi-thousand-line landings (reported only by vendors [sizing-review-23, sizing-lab-52]); which
  closing-note signals (a brief not needed, clean acceptance, no repair round) reliably show a
  ceiling can rise; independent tests of the newest coordination claims [sizing-lab-24,
  sizing-lab-29].

**Forecasts to score** (horizon 2027-03-31 unless stated):

| Id | Forecast | Falsified if |
| --- | --- | --- |
| TS1 | A lab or major harness vendor publishes task-size guidance larger than today's (for example Devin's three hours rises, or a Codex goal's "smaller than a backlog" is relaxed) | Every size rule named in F6 is unchanged or smaller |
| TS2 | METR, or another independent evaluator, publishes a p80 horizon above 4 hours for a released model | No independent p80 above 4 hours is published |
| TS3 | At least one major coding harness ships a first-class agent-owned plan or milestone artifact the person approves once (beyond Codex goals, Claude Code `/goal` and Factory Missions) | None ships |
| TS4 | An agent product ships a setting that governs when the agent may interrupt the person, as forecast in [sizing-prac-40] (horizon 2027-08-22) | None ships by the horizon |

## Sources

Every record's URL, quote and date is in [`_evidence/2026-09-26.jsonl`](../_evidence/2026-09-26.jsonl):
244 records, 240 from five parallel sweeps (lab and vendor guidance, measured horizons and
degradation, practitioners and aggregators, review and coordination costs, counter-forces and
trend), three copied forward from the 2026-09-25 file and re-verified, and one own check read in a
paper's full text. Each sweep copied quotes from raw page text, never from a model's paraphrase.
Every one of the 240 URLs was then fetched again and every quote matched verbatim (whitespace and
typographic quotes normalized): 212 at the cited URL, the other 28 through the route their record
names (arXiv full text for a quote cited at an abstract page, 11; arXiv MathML rendering, 2; a
verbatim mirror of a page that returned 403, 3; web.archive.org copies, 6; a docs page's Markdown
route, 2; a browser-rendered capture, 1; a site's JavaScript bundle, 1; a PDF whose hyphenation broke
the match, 1; an abstract's first version, 1). Three readers who wrote none of the records judged
each claim in context: 48 overstated (3 more flagged by the sweeps), 20 evidence classes changed
(mostly labs' claims about their own runs first labelled forecasts, and single reports first
labelled consensus), 5 author fields corrected; a rewritten record keeps its first wording in
`original_claim`, a reclassified one its first class in `original_evidence`. Two values extend the
shared fields: `evidence: forecast`, and `stance: observe` or `forecast`; undated documentation pages
carry `published: 2026-09`, the month they were read. By kind:

- **Anthropic:** Effective harnesses for long-running agents, 2025-11-26; Harness design for
  long-running application development, 2026-03-24; Effective context engineering for AI agents,
  2025-09-29; How we built our multi-agent research system, 2025-06-13; Building a C compiler with a
  team of parallel Claudes, 2026-02-05; How AI is transforming work at Anthropic, 2025-12-02;
  Measuring AI agent autonomy in practice, 2026-02-18; 2026 Agentic Coding Trends Report,
  2026-01-21; Bringing Code Review to Claude Code, 2026-03-09; How we contain Claude across products,
  2026-05-25; Introducing Claude Sonnet 4.5, 2025-09-29; Claude Fable 5 and Claude Mythos 5,
  2026-06-09; Introducing Claude Fable 5.1 and Claude Mythos 5.1, 2026-09; Claude Code docs (best
  practices, agent teams, goal) and the Claude Platform prompting pages (Opus 5, Opus 5.5, Fable 5
  and Fable 5.1 guides), read 2026-09-26.
- **OpenAI:** A practical guide to building agents, 2025-04; Harness engineering: leveraging Codex in
  an agent-first world, 2026-02-11 (via a verbatim mirror); Codex best practices, Follow a goal and
  subagents docs, read 2026-09-26; Using Goals in Codex, 2026-05-09; Using PLANS.md for multi-hour
  problem solving, 2025-10-14; Run long horizon tasks with Codex, 2026-02-23; Introducing upgrades to
  Codex, 2025-09-15, and Building more with GPT-5.1-Codex-Max, 2025-11-19 (via web.archive.org);
  Rethinking skills and prompts for GPT-6 Astra, 2026-09-11.
- **Other vendors:** Cursor, Scaling long-running autonomous coding, 2026-01-14, and Expanding our
  long-running agents research preview, 2026-02-12; Cognition, Don't Build Multi-Agents, 2025-06-12,
  Multi-Agents: What's Actually Working, 2026-04-22, Devin's 2025 Performance Review, 2025-11-14, and
  Devin docs (When to use Devin; Session Insights); Factory, Introducing Missions, 2026-02-26, and
  Missions docs; GitHub Copilot coding agent docs; Linear coding sessions docs; Google Antigravity
  CLI best practices; Amp Owner's Manual (November 2025 snapshot) and "200k Tokens Is Plenty",
  2025-12-09; Augment docs.
- **Measurement:** METR, Measuring AI Ability to Complete Long Tasks, 2025-03-18; Time Horizon 1.1,
  2026-01-29; Task-Completion Time Horizons of Frontier AI Models, 2026-05-08; Clarifying
  limitations of time horizon, 2026-01-22; How Does Time Horizon Vary Across Domains?, 2025-07-14;
  predeployment summaries for GPT-5.6 Sol, 2026-06-26, and Claude Opus 5.5, 2026-09-22; Algorithmic
  vs. Holistic Evaluation, 2025-08-13; Many SWE-bench-Passing PRs Would Not Be Merged into Main,
  2026-03-10; the developer productivity study, 2025-07-10, and its update of 2026-02-24 (read
  2026-10-01); Recent Frontier Models Are Reward Hacking, 2025-06-05. Toby Ord, Is there a Half-Life
  for the Success Rates of AI Agents?, 2025-05-07, updated 2026-02-04. Epoch AI, MirrorCode,
  2026-04-10. Chroma, Context Rot, 2025-07-14. arXiv: 2509.09677, 2511.09030, 2505.23419
  (SWE-bench-Live), 2509.16941 (SWE-Bench Pro), 2512.18470 (SWE-EVO), 2608.09802 (ProMax),
  2609.01271, 2603.24755 (SlopCodeBench), 2608.16370, 2608.06503, 2606.14066 (FastContext),
  2503.13657 (MAST), 2601.13295 (CooperBench), 2608.00947, 2512.08296, 2609.19759, 2608.23395,
  2605.15425, 2606.20695, 2601.15195, 2605.22534, 2601.18749, 2601.00753, 2604.03551, 2607.04697,
  2606.15689, 2605.11495 (Hedwig), 2602.03412, 2609.20812, 2605.12366, 2606.05391, 2609.20804,
  2605.21384, 2606.28430, 2504.16563, 2607.07593, 2602.11988, 2602.14611.
- **Review and delivery:** SmartBear/Cisco case study, 2006, and best-practices page; Sadowski et
  al., Modern code review at Google, 2018; Bosu et al., useful code review comments, 2015; Baum,
  Schneider and Bacchelli, EMSE 2019; Bacchelli and Bird, ICSE 2013; Google eng-practices, small CLs;
  Graphite, the ideal PR is 50 lines, 2023; LinearB 2026 benchmarks; Faros AI, The AI Productivity
  Paradox Report 2025, 2025-07-23; DORA 2024 report and working-in-small-batches capability;
  Innolution on Reinertsen's batch-size economics, 2016.
- **Writing and readability:** NN/g, Morkes and Nielsen, Concise, SCANNABLE, and Objective, 1997; NN/g
  on F-shaped and layer-cake scanning, 2019; NN/g inverted pyramid and progressive disclosure; Google
  Technical Writing, "Documents"; Google developer documentation style guide (tables); US federal
  plain-language guidelines; Diátaxis; the Rust RFC template; design docs at Google.
- **Ticket systems:** mattpocock/skills v1.2.3 and `skills/engineering/wayfinder` (MIT, 2026-08-19);
  BMAD 6.12; OpenSpec 1.13; Doorstop; OpenFastTrace; HumanLayer commands; CCPM; Spec Kit; Beads;
  Epiq; git-bug; GitHub issue dependencies, sub-issues and `gh` 2.101.0; GitHub and GitLab
  merge-method documentation; Gerrit Change-Id; Jujutsu change ids; read 2026-09-19 to 2026-09-23.
- **Practitioners and aggregators:** Latent Space — The Age of Async Agents (Cognition's Walden Yan
  and OpenInspect's Cole Murray, 2026-05-28), Extreme Harness Engineering for Token Billionaires (Ryan
  Lopopolo, 2026-04-07), The Evolution of the Agent Harness (Dan McAteer, 2026-08-22); Simon
  Willison — parallel coding agents, 2025-10-05, agentic engineering anti-patterns, about 2026-03,
  The AI Vampire, 2026-02-15; Karpathy — YC keynote, 2025-06-18, and January 2026 post; Harper Reed,
  2025-02-16; Addy Osmani, 2026-01-04 and 2026-06-15; Mitchell Hashimoto, 2026-02-05; Kent Beck,
  2026-04-23; Geoffrey Huntley, Ralph, 2025-07-14 and ghuntley.com/loop, 2026-01; Steve Yegge, Gas
  Town, 2026-01-01; Stripe minions, 2026-02-09; Spotify Honk, 2025-11-24 and 2025-12-09; Ramp
  Inspect, 2026-01-12; Airbnb test migration, 2025-03-13; Peter Steinberger, 2025-10-14 and
  2025-12-28; Armin Ronacher, 2026-02-13 and 2026-06-23; Scott Logic, 2026-05-14; AI 2027 timelines
  update, 2025-05-07; TechCrunch on OpenAI's research goals, 2025-10-28; a Hacker News scan of
  spec-driven work, 2026-05 to 2026-09.
- **Read 2026-10-01 for later additions:** EARS (alistairmavin.com/ears); Cucumber, Example Mapping
  introduction; secondary accounts of Alan Klement's job story (2013); Bansal et al., Does the Whole
  Exceed its Parts?, CHI 2021, arXiv 2006.14779. One repository's records: the ledger's audit, the
  tracker's body-size scan, the feasibility record of the compiled-brief runs, a model judge's
  reading of four breakdowns, and an audit of one repository's process gate.
