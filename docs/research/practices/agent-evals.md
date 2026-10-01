---
last_checked: 2026-10-01
volatility: STABLE (suite method, statistics, error analysis, SQL correctness) / VOLATILE (§8 what evaluation tools ship)
sources:
  - https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
  - https://hamel.dev/blog/posts/evals-faq/
  - https://arxiv.org/abs/2406.12045
  - https://arxiv.org/abs/2411.00640
  - https://www.anthropic.com/research/statistical-approach-to-model-evals
  - https://www.anthropic.com/engineering/infrastructure-noise
  - https://arxiv.org/abs/2607.27250
  - https://arxiv.org/abs/2609.19607
  - https://arxiv.org/abs/2010.02840
  - https://arxiv.org/abs/2402.12243
  - https://arxiv.org/abs/2601.08778
  - https://inspect.aisi.org.uk/scoring-workflow.html
  - https://www.promptfoo.dev/docs/usage/command-line/
  - https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators
  - https://langfuse.com/resources/engineering/ai-agent-evaluation
---

# Evaluating agent systems: suites, statistics, error analysis, SQL correctness

Re-check when an evaluation tool changes what it ships, a lab revises its agent-eval guidance, or
a study revises the statistics of agent evals or the error rates of a text-to-SQL benchmark.

How to build and read an evaluation suite for an agent or a model-backed system: which suites to
keep, what to grade, how many runs and tasks a comparison needs and how to compare two variants,
how to find failures by reading traces, how to check generated SQL, and what evaluation tools ship.
For anyone who designs an eval suite or a release gate, compares two prompts, models or agent
versions, or chooses an evaluation tool. Model judges (prompting, biases, calibration,
consistency) are in [llm-as-judge.md](llm-as-judge.md); OutcomeBound's own evaluations, their
method and their limits are in [evaluations.md](evaluations.md).

**Evidence classes.** (M) measured; (L) a lab's or vendor's documentation or guidance; (S) a
standard; (P) practitioner consensus; (A) an anecdote or one person's view; (F) a forecast; (O)
OutcomeBound's own runs. "(inference)" marks a step this reference draws from the cited evidence.
**Citations.** Bracketed ids resolve by `id` in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl); papers and pages are listed under
Sources with the day they were read, every one 2026-10-01.

**Structure against numbers.** The structural claims below are shared across the sources; the
specific numbers (trace counts, a 60–80% share of effort on error analysis, pass-rate targets, two-
to four-week cycles) are practitioner heuristics, which the Husain and Shankar FAQ itself presents
as "sharp opinions about what works in most cases. They are not universal truths" (P).

## 1. Suite structure

- **Two kinds of suite, and a path between them.** Capability evals ask "What can this agent do
  well?" and should start at a low pass rate, on tasks the agent struggles with; regression evals
  ask whether it still handles what it used to and should pass nearly 100%. As capability evals
  saturate they can graduate into the regression suite (L, Anthropic, Demystifying evals for AI
  agents). "If you're passing 100% of your evals, you're likely not challenging your system
  enough. A 70% pass rate might indicate a more meaningful evaluation" (P, evals FAQ). One suite
  serving both questions answers neither well: pinned at 100% it shows no improvement, and below
  it a drop cannot be told from a hard case (inference).
- **Start small.** Anthropic sees teams delay evals because they think they need hundreds of
  tasks: "20-50 simple tasks drawn from real failures is a great start", since early changes have
  large effects that small samples can see (L).
- **What the method assumes and is easy to skip** (L, Anthropic):
  - Balance: "Test both the cases where a behavior should occur and where it shouldn't. One-sided
    evals create one-sided optimization."
  - A reference solution for each task, "a known working output that passes all graders", which
    proves the task solvable and the grader wired.
  - Isolation: "Each trial should be isolated by starting from a clean environment"; shared state
    causes correlated failures and can inflate results, as when Claude gained "an unfair advantage
    on some tasks by examining the git history from previous trials".
- **A deterministic floor first.** Code-based graders are "fast, cheap, objective, reproducible,
  and easy to debug" (L, Anthropic); favour assertions and other deterministic checks over model
  judges, which are for failures that need human judgment (P, evals FAQ); "Use deterministic code
  checks for anything decidable, LLM-as-a-judge for semantic judgments, and human annotation to
  calibrate both" (L, Langfuse). Where a judge is used, decompose its criteria into binary checks
  rather than a 1–5 scale ([llm-as-judge.md](llm-as-judge.md#3-prompting-a-judge)).
- **Read the transcripts.** "You won't know if your graders are working well unless you read the
  transcripts and grades from many trials" (L, Anthropic).

## 2. Outcome and trajectory

- **The outcome is the gate; the path is diagnostic.** "It's often better to grade what the agent
  produced, not the path it took", so valid routes the designer did not anticipate are not
  penalised (L, Anthropic). Husain and Shankar evaluate an agent in two phases: end-to-end task
  success first, treating the agent as a black box, then step-level diagnostics once error
  analysis shows which workflows fail (P).
- **State path expectations as properties, not golden sequences.** Langfuse scores trajectories by
  decidable properties (step counts, loop detection, required steps present, budget checks) and
  codifies a bad trajectory as a property ("must not call the payment tool twice") (L). Express a
  path as required and forbidden calls, an ordering only for the few pairs where order is a safety
  matter, and ceilings on steps and cost (inference).
- **Match modes the tools ship.** Vertex AI's trajectory metrics offer exact match, in-order match
  (all reference calls in order, extra calls allowed), any-order match, and precision and recall
  over tool calls (L); Microsoft Foundry's task navigation efficiency evaluator offers
  `exact_match`, `in_order_match` and `any_order_match` (L); LangChain's agentevals offers
  `strict`, `unordered`, `subset` and `superset` (L). If a path must be matched at all, a subset,
  superset or precision–recall reading tolerates valid variation that a strict match fails
  (inference).

## 3. Statistics: pass^k, standard errors, paired comparisons

- **pass@k and pass^k.** pass@k is the chance of at least one success in k attempts, pass^k the
  chance that all k succeed: "If your agent has a 75% per-trial success rate and you run 3 trials,
  the probability of passing all three is (0.75)³ ≈ 42%" (L, Anthropic). τ-bench defined pass^k
  as the chance that all k independent trials of a task succeed; its strongest function-calling
  agent, gpt-4o, succeeded on under 50% of tasks, and its pass^8 in the retail domain was below
  25% (M, arXiv 2406.12045; [evals-2] detail). Use pass@k for "can it ever", pass^k for behaviour
  that must hold every time ([`writing-for-models.md`](writing-for-models.md) §9.1 item 7).
  Multi-trial statistics hold only if the trials are isolated (§1).
- **Standard errors.** Report the standard error with every score; cluster it on the unit of
  randomisation when questions come in groups (clustered standard errors on popular evals ran over
  three times the naive ones); and compare two variants by paired differences on the same
  questions, since frontier models' per-question scores correlate 0.3 to 0.7 (L, Anthropic's
  statistical approach to model evals; M, arXiv 2411.00640; [evals-16]). Miller computes standard
  errors from the Central Limit Theorem and regards bootstrapping "as unnecessary unless a
  complicated sampling scheme or estimator is being used" (M, arXiv 2411.00640). Do not lower the
  sampling temperature to cut variance unless the model at that temperature is the subject;
  resample and average per question instead (M, arXiv 2411.00640).
- **Infrastructure and time.** On Terminal-Bench 2.0 the most- and least-resourced setups
  differed by 6 points (p < 0.01); pass rates were seen, anecdotally, to vary with the time of
  day, and for evals meant to be shared the advice is to run at several times and on several days
  (L, Anthropic's infrastructure-noise post; [evals-20]). Running compared arms close together in
  time, or interleaved, keeps that drift out of the difference (inference).
- **When the machinery is needed.** Paired, question-level analysis with uncertainty bounds is
  required where a judged or sampled aggregate gates a release; where scores only advise, the
  machinery can wait until they gate (inference).
- **Tools.** inspect-ai ships standard errors clustered on a key, a bootstrapped standard error,
  Student-t or cluster-bootstrap confidence intervals and a Wilson interval for binary scores (L);
  Microsoft's ai-agent-evals GitHub Action reports confidence intervals and a test of statistical
  significance for each agent against a baseline agent (L). Whether other platforms ship
  baseline-relative statistics was not checked.

## 4. Task selection

- **Task count matters more than repeats.** A power simulation of a context-file ablation on two
  coding agents found more tasks buying far more power than more repeats; its figures, and what
  they mean for a suite of a few fixtures, are in
  [evaluations.md](evaluations.md#runs-per-cell-and-power) (M, arXiv 2607.27250).
- **Tasks that can move.** One ablation screened 84 candidate tasks for the band where an agent
  sometimes passes, "to avoid a floor/ceiling design" (M, arXiv 2607.27250; [evals-18]). In
  DeepSWE's published trials only 22 of 113 tasks (19.5%) had single-run results whose
  fifth-percentile correlation with full-benchmark performance reached 0.50; DeltaSelect ranks
  every task by that reliability and fills a fixed budget, and is "intended for repeated
  baseline-versus-candidate comparisons during development, not model rankings" (M, arXiv
  2609.19607).

## 5. Error analysis

- **The method.** Husain and Shankar's evals FAQ: start with 100 diverse traces and annotate at
  least the first 30 yourself; write open-ended notes on what went wrong (open coding), group them
  into a failure taxonomy (axial coding), and continue until new traces stop revealing failure
  modes or changing existing ones (theoretical saturation), reviewing at least 100 and going past
  that while still learning; review cycles they have seen run two to four weeks, with 10 to 20
  traces a week between, focused on outliers (unusually long conversations, sessions with
  retries, traces flagged by automated monitoring); in a multi-turn trace look for the first
  upstream failure, and where tools or several agents are involved use a transition failure
  matrix, rows the last successful state and columns where the first failure occurred (P,
  hamel.dev evals FAQ, revised 2026-09-21). In their projects 60 to 80% of development time went
  to error analysis and evaluation (P).
- **Sampling.** Random, clustering, classifier-flagged and feedback-selected (negative user
  feedback) samples run from most exploratory to most targeted; "Keep some random traces in every
  batch", so failure modes the current signals do not describe can still be found (P, evals FAQ).
- **From production failure to regression case.** "When production monitoring reveals new failure
  patterns through error analysis and evals, add representative examples to your CI dataset"
  (P, evals FAQ); Langfuse's loop collects failing production traces, turns them into dataset
  items and reproduces the failure in an experiment (L). A raw failure becomes a permanent case
  only after a person confirms it is a failure, representative and stable, and the case has an
  oracle independent of the system under test (inference).

## 6. Judge validity in a suite

A judge's agreement with itself is not its validity: validate it against expert labels (true
positive and true negative rates), record its identity with every result and derive thresholds
again when it changes. The evidence is in [llm-as-judge.md](llm-as-judge.md#1-consistency-is-not-validity)
and [llm-as-judge.md](llm-as-judge.md#6-when-the-judge-changes-calibration).

## 7. Text-to-SQL correctness

- **Execution accuracy is the standard.** A predicted query is scored by executing it and
  comparing its result with the gold result, and the evaluators differ in how they compare. BIRD's
  executes the predicted and the gold query and compares the two results as sets of rows, so
  duplicates and row order do not count (L, BIRD `evaluation.py` and mini-dev `evaluation_ex.py`).
  The distilled test-suite evaluator compares results as multisets of rows, allows a permutation
  of columns, and treats row order as significant only when the gold query has `ORDER BY` (L,
  test-suite-sql-eval `exec_eval.py`). Spider 2.0's compares the prediction's result with one or
  more stored gold results, numbers within an absolute tolerance of 0.01 and a missing value
  counted as 0 (L, Spider 2.0 `evaluate.py`). Compare as multisets, and as sequences only where
  the gold query orders its rows; use a judge only where execution cannot decide (inference).
- **Keep gold queries, not only gold rows.** A gold query can be executed against each database
  state a check uses and again after the data changes, while stored rows go stale silently when
  the data does; run both against a frozen snapshot so a result changes only when a query does
  (inference from the test-suite method below).
- **One database state passes wrong queries.** Checking a query against the one released database
  passed wrong queries 6.5% of the time on average and up to 9.0%, and 11.0% on average and up to
  17.6% on the hardest queries; a suite of about 42 distilled databases per query was correct on
  100 hand-checked examples (M, arXiv 2010.02840). A check against one fixture state can pass a
  wrong change that agrees on that state; OutcomeBound's ladder probe on recorded stock is a second
  state of that kind ([evaluations.md](evaluations.md) E8).
- **Gold queries are often wrong.** Audits of text-to-SQL benchmarks found wrong gold queries in
  5% to 40% of sampled BIRD domains (20.7% in the largest sample) (M, arXiv 2402.12243), and
  annotation errors, from wrong ground truth to ambiguous questions, in 52.8% of BIRD Mini-Dev and
  62.8% of Spider 2.0-Snow examples (M, arXiv 2601.08778; the CIDR 2026 version gives 66.1% for
  the second). BIRD released a cleaned dev set in 2023, which raised ChatGPT's and GPT-4's execution
  accuracy from 37.22 to 42.24 and 46.35 to 49.15, and a cleaner dev split on 2025-11-13 (L, BIRD
  page). If published benchmarks carry these rates, a project's own gold queries need the same
  audit, repeated as the schema and data change (inference).
- **Extra columns.** Spider 2.0's evaluator passes a prediction when every gold column (or every
  column the task marks as a condition) matches some predicted column by value, so superfluous
  columns and column names do not fail it (L, Spider 2.0 `evaluate.py`). Where returning a column
  nobody asked for can be an authorization or data-minimization failure, an unexpected column is a
  finding, not noise, and a check should not inherit that tolerance (inference).

## 8. What evaluation tools ship (VOLATILE)

- **Score apart from generation.** inspect-ai's `--no-score` writes a log without scoring, and
  `inspect score` scores it later; `--action append` adds new scores beside the old, `--action
  overwrite` replaces them, so a grader can be iterated on stored transcripts without paying for
  generation again (L).
- **Named, frozen dataset versions.** LangSmith versions a dataset on every change, tags a version
  by timestamp (`as_of`) with a name such as "prod", and evaluates on a tagged version (L); Phoenix
  experiments take a `dataset_version_id`, defaulting to the latest version (L, phoenix-client
  source).
- **The verdict in the output.** Microsoft Foundry's general-purpose evaluators return each score
  with a label, a reason, a threshold and a pass flag (default threshold 3 on a 1–5 scale), so no
  reader re-derives a pass (L).
- **Report before gating; quarantine without deleting.** DeepEval's `threshold=None` runs a metric
  in score-only mode, computed and reported with no pass or fail; a metric marked `flaky` is
  computed and reported but never decides its test case's status, and every test case needs at
  least one non-flaky metric with a threshold (L).
- **Judge hardening.** inspect-ai's model grader binds to the last `GRADE:` in the judge's output
  ([evaluations.md](evaluations.md#lessons-on-eval-design), lesson 5) and accepts a panel of grader
  models decided by majority ([llm-as-judge.md](llm-as-judge.md#2-biases)).
- **Re-run only what failed.** promptfoo re-runs only the failures of a previous eval with
  `--filter-failing` (given a file path or an eval id), only assertion failures with
  `--filter-failing-only`, and only errors with `--filter-errors-only` (L).
- **Retries.** inspect-ai's `--retry-on-error` records the errors that caused each retry in the
  sample's `error_retries` field, and warns that silent retries shift the distribution toward
  inputs that pass on a re-roll ([evaluations.md](evaluations.md#lessons-on-eval-design), lesson
  11).
- **Gates.** promptfoo's `eval` exits with code 100 when a test fails or the pass rate falls below
  `PROMPTFOO_PASS_RATE_THRESHOLD` (default 100%) (L); Braintrust's `bt eval` exits non-zero only
  when an eval throws, and leaves pass and fail to custom reporters (L); Microsoft's ai-agent-evals
  action compares agents against a baseline agent with significance tests (§3). None of the pages
  read describes a built-in gate on a regression relative to a baseline.
- **OpenAI's Evals platform is deprecated** (notice of 2026-06-03): existing evals become read-only
  on 2026-10-31, and the dashboard and API are scheduled to shut down on 2026-11-30, with promptfoo
  named as a migration path (L).

## 9. Contested points (MONITOR)

- **Trajectory evaluation.** Anthropic prefers grading the outcome over the path (L); Vertex AI,
  Microsoft Foundry and LangChain ship trajectory matchers (L); Langfuse treats the trajectory as
  one of four dimensions, scored by properties and budgets rather than exact sequences (L). What
  remains disputed is matching a golden sequence, not measuring the path.
- **Evals before the feature.** Husain and Shankar: "Should I practice eval-driven development?
  Generally no", since an LLM's failure modes cannot be anticipated (P); Anthropic: "We recommend
  practicing eval-driven development: build evals to define planned capabilities before agents can
  fulfill them" (L).
- **Where a gate's threshold lives, and what it compares.** An absolute floor (promptfoo's pass
  rate) or a regression against a baseline (§3, §8); a threshold kept in the evaluation platform
  or in the code under review. No source read settles either.
- **How much production traffic to judge.** Husain and Shankar's example runs cheap checks on every
  trace and an expensive judge on a nightly sample (P); Langfuse controls online evaluation cost by
  sampling a percentage of traces (L). No source read gives a principled sampling rate.

## How to apply

1. Keep a capability suite and a regression suite, graduate cases between them, and include cases
   where the behaviour should not occur (§1).
2. Give every task a reference solution and a clean environment per trial (§1).
3. Grade the outcome with deterministic checks first; state path expectations as properties and
   budgets (§1, §2).
4. Report standard errors, clustered where questions are grouped, and compare variants by paired
   differences on the same questions; run compared arms close together in time (§3).
5. Choose tasks the agent sometimes passes, and prefer more tasks to more repeats (§4).
6. Find failures by reading traces to saturation before writing evaluators, and turn confirmed,
   representative failures into regression cases (§5).
7. For generated SQL, execute and compare results as multisets, against several database states,
   and audit the gold queries (§7).

## Limits

- The suite-design guidance is a lab's and practitioners' (L, P); its numbers are heuristics.
- The power results are one simulation on two coding agents; the text-to-SQL error rates are
  audits of public benchmarks, not of any project's own gold queries.
- §8 records what each tool's documentation said on 2026-10-01; whether a tool lacks a feature was
  checked only where stated.

## Sources

All read 2026-10-01.

- Anthropic, "Demystifying evals for AI agents" (2026-01-09),
  <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>.
- Husain and Shankar, evals FAQ (published 2026-09-18, modified 2026-09-21),
  <https://hamel.dev/blog/posts/evals-faq/>.
- τ-bench, <https://arxiv.org/abs/2406.12045>; Miller, "Adding Error Bars to Evals", arXiv
  2411.00640 (2024-11-01), <https://arxiv.org/abs/2411.00640> (abstract and HTML); Anthropic, "A
  statistical approach to model evals" (2024-11-19),
  <https://www.anthropic.com/research/statistical-approach-to-model-evals>; Anthropic,
  "Quantifying infrastructure noise in agentic coding evals" (2026-02-05),
  <https://www.anthropic.com/engineering/infrastructure-noise>.
- The two-agent context-file ablation, <https://arxiv.org/html/2607.27250>; DeltaSelect,
  <https://arxiv.org/abs/2609.19607>.
- Zhong, Yu and Klein, distilled test suites, <https://arxiv.org/abs/2010.02840>, and its
  evaluator, <https://github.com/taoyds/test-suite-sql-eval> (`exec_eval.py`); BIRD noise,
  <https://arxiv.org/abs/2402.12243>; text-to-SQL annotation errors,
  <https://arxiv.org/abs/2601.08778> and
  <https://vldb.org/cidrdb/2026/text-to-sql-benchmarks-are-broken-an-in-depth-analysis-of-annotation-errors.html>;
  BIRD, <https://bird-bench.github.io/>, and its evaluators,
  <https://github.com/AlibabaResearch/DAMO-ConvAI> (`bird/llm/src/evaluation.py`) and
  <https://github.com/bird-bench/mini_dev> (`evaluation/evaluation_ex.py`); Spider 2.0, <https://spider2-sql.github.io/> and its
  evaluator, <https://github.com/xlang-ai/Spider2> (`spider2-lite/evaluation_suite/evaluate.py`).
- inspect-ai: scoring workflow, <https://inspect.aisi.org.uk/scoring-workflow.html>; options,
  <https://inspect.aisi.org.uk/options.html>; scoring metrics,
  <https://inspect.aisi.org.uk/metrics.html>; handling errors,
  <https://inspect.aisi.org.uk/handling-errors.html>.
- LangSmith, manage datasets, <https://docs.langchain.com/langsmith/manage-datasets>; LangChain
  agentevals, <https://github.com/langchain-ai/agentevals>; Phoenix client source,
  <https://github.com/Arize-ai/phoenix> (`packages/phoenix-client`).
- Microsoft Foundry: general-purpose evaluators,
  <https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/general-purpose-evaluators>;
  agent evaluators,
  <https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators>;
  ai-agent-evals action, <https://github.com/microsoft/ai-agent-evals>.
- Vertex AI, evaluate agents,
  <https://cloud.google.com/vertex-ai/generative-ai/docs/models/evaluation-agents>.
- DeepEval, metrics, <https://deepeval.com/docs/metrics-introduction>.
- promptfoo, command line, <https://www.promptfoo.dev/docs/usage/command-line/>.
- Braintrust, run experiments in CI/CD, <https://www.braintrust.dev/docs/evaluate/run-in-ci>.
- Langfuse, AI agent evaluation, <https://langfuse.com/resources/engineering/ai-agent-evaluation>,
  and LLM-as-a-judge, <https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge>.
- OpenAI deprecations, <https://developers.openai.com/api/docs/deprecations>.
