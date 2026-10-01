---
last_checked: 2026-10-01
volatility: STABLE (bias, validity and consistency findings are structural) / MONITOR (§4 reasoning effort for judges is active research; vendor rules on sampling parameters change with releases)
sources:
  - https://arxiv.org/abs/2606.19544
  - https://arxiv.org/abs/2606.13685
  - https://arxiv.org/abs/2607.08535
  - https://arxiv.org/abs/2508.06709
  - https://arxiv.org/abs/2410.21819
  - https://arxiv.org/abs/2604.22891
  - https://arxiv.org/abs/2410.12784
  - https://arxiv.org/abs/2603.12246
  - https://arxiv.org/abs/2604.26954
  - https://arxiv.org/abs/2406.12624
  - https://arxiv.org/abs/2606.09410
  - https://hamel.dev/blog/posts/evals-faq/
  - https://developers.openai.com/api/docs/guides/reasoning-best-practices
  - https://developers.openai.com/api/docs/guides/latest-model
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5
---

# Model judges: validity, biases, prompting, calibration, consistency

Re-check when a study measures how a judge's reasoning effort changes its accuracy, a judge model
is swapped, or a provider changes which sampling parameters its reasoning models accept.

What a language model used as a judge (LLM-as-judge) can be trusted to measure, which biases it
carries, how to prompt it, what to do when the judge changes, how much reasoning effort it needs,
and how far repeated calls agree. For anyone who scores model or agent output with another model,
chooses or swaps a judge, or reads a judged result. OutcomeBound's own judged probes, and the
limits that follow from them, are in [evaluations.md](evaluations.md) (E11, E13 to E15, lesson
12); suite design, statistics and error analysis are in [agent-evals.md](agent-evals.md).

**Evidence classes.** (M) measured; (L) a lab's or vendor's documentation or guidance; (S) a
standard; (P) practitioner consensus; (A) an anecdote or one person's view; (F) a forecast; (O)
OutcomeBound's own runs. "(inference)" marks a step this reference draws from the cited evidence.
**Citations.** Papers by arXiv number and pages by name, listed under Sources with the day they
were read; every source was read 2026-10-01.

## 1. Consistency is not validity

- **Agreement with itself does not show a judge is right.** Across 21 judges from nine providers
  and about 541,000 judgments over 118 runs on MT-Bench, JudgeBench and RewardBench, every judge's
  exact-match agreement exceeded its chance-corrected agreement (Cohen's κ) on MT-Bench by 33.8 to
  41.2 points; judge rankings shifted by up to 14 positions across benchmarks; and two production
  judges combined test-retest reliability above 0.95 with position bias above 0.10 (Qwen 3 8B,
  0.992 and 0.192; Gemini 2.5 Flash, 0.988 and 0.125) (M, arXiv 2606.19544). A judge that repeats
  itself can be wrong the same way every time; only agreement with labelled cases shows it is
  right.
- **Judges lean lenient.** Thirteen judges grading nine exam-taker models, in a setting where
  people agreed with each other well, fell short of that human agreement even at the largest
  sizes, could assign scores up to 5 points from the human ones, and tended toward leniency:
  calling an answer correct when it did not fully meet the criteria. Judges with high percent
  agreement still assigned very different scores (M, arXiv 2406.12624).
- **Agreement on rankings can hide disagreement on items.** Over 105,600 evaluation instances
  from 32 models, judges agreed almost perfectly on which model was better (Spearman ρ = 0.99)
  and much less on each sample (mean Pearson r = 0.72), anchoring scores on shared surface
  features rather than substance (M, arXiv 2603.11027).
- **Validate against people, on both classes.** Measure a judge's true positive rate (failures
  it catches) and true negative rate (good outputs it passes) against labels from a trusted domain
  expert; split the labelled examples into train (10 to 20%, the ones that may appear in the
  prompt), dev (40 to 45%) and test (40 to 45%), with 30 to 50 passes and 30 to 50 fails in each
  of dev and test (P, Husain and Shankar's evals FAQ, which calls itself "sharp opinions about what
  works in most cases"). Anthropic: model-based graders "should be closely calibrated with human
  experts" (L, Demystifying evals for AI agents).

## 2. Biases

- **Judges prefer their own text and their own family's.** GPT-4o and Claude 3.5 Sonnet scored
  their own outputs higher and also favoured other models of their own family (M, arXiv
  2508.06709); that study's judge prompts carried only the task and the answer, no model name, so
  hiding the author's name did not remove the preference. GPT-4's self-preference tracks
  familiarity: judges scored lower-perplexity text higher whether or not they wrote it (M, arXiv
  2410.21819). Across 20 models, stronger capability was often uncorrelated, or even negatively
  correlated, with low self-preference (M, arXiv 2604.22891): a stronger judge is not a less
  self-preferring one, and can be more.
- **Position.** In pairwise judging, GPT-4o-mini picked the first position in 72% of its
  majority verdicts (p = 0.024) (M, arXiv 2606.13685), and two production judges showed position
  bias above 0.10 (§1). A pointwise score has no order between candidates to bias; but in the same
  study the judges' pointwise score gaps were small (0.19 to 0.36 on a 10-point scale) and not
  significant in aggregate where their pairwise calls still named a winner (M, arXiv 2606.13685).
  Eugene Yan's survey reports pairwise comparison as more stable than direct scoring for
  subjective tasks and direct scoring as preferable for objective ones (P).
- **Length.** Judges have been reported to favour longer answers that are not clearer (P, Eugene
  Yan's survey); stronger judges reduced verbosity bias without removing it (M, arXiv 2607.08535);
  and under one pairwise rubric across 21 judges the measured verbosity bias was small, below
  0.011 (M, arXiv 2606.19544). The size depends on the rubric and the judge, so a rubric line such
  as "do not reward length; judge information density against the request" is cheap insurance
  (inference).
- **Mitigations.**
  - A panel of judges from several families: 2508.06709 recommends one drawn from multiple
    families (GPT, Claude, Llama), and a panel of smaller models from disjoint families showed less
    intra-model bias than one large judge (M, arXiv 2404.18796). inspect-ai's model-graded scorers
    accept a list of grader models and decide by majority, a grade winning only when more than
    half the panel returns it (L, inspect-ai model-graded scorers).
  - Criteria a check can settle: a structured, multi-dimensional evaluation reduced
    self-preference by 31.5% on average (M, arXiv 2604.22891).
  - Removing the author's name alone is not enough (above).
- **Contested: the same model as task model and judge.** Husain and Shankar hold that using the
  same model is usually fine, because the judge does a different, scoped binary task and what
  matters is its agreement with human labels; they would try another model only when alignment
  fails (P). The studies above measure a preference for one's own family. Both lead to the same
  check: validate the judge against labelled cases, and keep a cross-family spot-check where the
  judge shares a family with what it scores (inference).

## 3. Prompting a judge

- **No reasoning scaffolding for a reasoning model.** "Avoid chain-of-thought prompts: Since these
  models perform reasoning internally, prompting them to 'think step by step' or 'explain your
  reasoning' is unnecessary" (L, OpenAI reasoning best practices). The same guidance asks to "be
  very specific about your end goal" and its success criteria.
- **Rubric content still matters.** Rubrics built with domain knowledge raised human-judge
  agreement in knowledge-rich domains (Education +22%, Academic +27%) and lowered it in subjective
  ones (M, arXiv 2603.11027); a framework that locks the rubric, grounds each score in evidence
  from the answer and calibrates the scale improved agreement with human scores across four
  benchmarks (M, arXiv 2601.08654). Write criteria as atomic checks with what separates adjacent
  scores, and give the judge the domain facts it needs (inference).
- **Binary checks over 1–5 scales.** Husain and Shankar: "Binary evaluations force clearer
  thinking and more consistent labeling"; the gap between adjacent Likert points is subjective and
  inconsistent across annotators, detecting differences needs larger samples, and annotators drift
  to the middle. To track gradual improvement, count binary sub-checks ("4 out of 5 expected facts
  included") rather than rate on a scale (P, evals FAQ).
- **Criteria drift.** "Users need criteria to grade outputs, but grading outputs helps users
  define criteria" (M, arXiv 2404.12272): a rubric written before the answers are read changes
  once they are, which is one way a rubric falls out of step with the text it scores
  ([evaluations.md](evaluations.md#lessons-on-eval-design), lesson 12).
- **Ask for coverage, filter downstream.** Anthropic's prompting guides for Claude Opus 4.8,
  Claude Sonnet 5 and Claude Opus 5: a review prompt that says "only report high-severity issues",
  "be conservative" or "don't nitpick" may be followed literally, so the model investigates as
  deeply but reports fewer findings; precision rises and measured recall falls. The suggested
  wording asks for every issue, with a confidence and an estimated severity for each, so a separate
  step can filter (L). The same holds for a judge asked to flag defects: wording that asks for
  certainty lowers recall, wording that asks for coverage raises it at the cost of false positives
  (inference).
- **Structured output.** Models with headroom absorbed a JSON schema without loss (Claude Sonnet,
  88.7 ± 4.0% with JSON against 89.3 ± 1.7% with free chain of thought on MATH-Hard); models near
  their limits lost 28.0 to 36.2 points; reasoning freely before formatting recovered most of the
  loss (M, arXiv 2606.09410). A reasoning model reasons before it writes its final output, so a
  strict schema on the verdict is the "think first, format later" arrangement; a short rationale
  field kept for audit costs little, and its order in the schema matters less for a reasoning
  judge than for one that reasons only in its output (inference).
- **Context.** Give each judge only the parts of the trace its failure mode needs; extra context
  can make it worse, and an ablation against human labels shows what can be left out (P, evals
  FAQ). When a rubric scores an answer's structure, cutting the answer's end removes what is
  scored: keep the head and the tail, or raise the cap (inference).
- **Parse the verdict so the judged answer cannot supply it.** inspect-ai binds to the last
  `GRADE:` in the judge's output ([evaluations.md](evaluations.md#lessons-on-eval-design), lesson
  5).

## 4. Reasoning effort and optimisation pressure (MONITOR)

- **Hard discrimination rises with effort.** On JudgeBench's challenging response pairs, o3-mini
  as a judge scored 80.86%, 76.57% and 70.57% at high, medium and low reasoning effort (M, arXiv
  2410.12784).
- **Scoring against a rubric.** On automated scoring with models from OpenAI and Google (among
  them Gemini 3.1 Pro Preview, GPT-5.4 Nano and GPT-5.4 Mini), higher reasoning effort showed a
  significant positive linear trend with accuracy; temperature sampling beat deterministic calls,
  but ensembles of 1 to 7 calls added no significant gain; model choice and reasoning settings
  mattered more than ensembling (M, arXiv 2604.26954, abstract).
- **Optimisation pressure.** Used as the reward in training, non-reasoning judges were
  reward-hacked easily, and policies trained against reasoning judges learned adversarial outputs
  that also deceived other LLM judges on Arena-Hard (M, arXiv 2603.12246): a judge that something
  is optimised against gets gamed. The same study found the reasoning judge's benefit depended on
  "a sufficiently high reasoning effort" and on distilling the gold-standard judge's reasoning;
  at lower effort the trained policies reward-hacked as with non-reasoning judges (M).
- **What to do.** The measured trend favours more effort, by an amount that differs by task and
  model; compare two effort levels on your own labelled calibration set before choosing, rather
  than defaulting to the highest (inference).

## 5. Consistency and repeated calls

- **A verdict varies between identical calls.** With two judges (GPT-4o-mini and GPT-4.1-mini)
  over 29 tasks in 10 categories at temperature 1.0, pairwise preferences flipped on average 13.6%
  of the time between repeated calls, 28% of questions flipped more than 20% of the time and one
  56%; a single call recovered the 50-trial majority verdict 86.6% of the time, about 3 calls
  reached 90%, and a majority vote needed 11 trials on average, 15 on high-variance questions, to
  recover it with 95% probability. The two judges agreed with each other on 76% of verdicts
  (κ = 0.51), and semantically equivalent prompt templates changed the majority outcome in 25% of
  tested cases (M, arXiv 2606.13685).
- **Temperature 0 is not invariance.** At temperature 0 GPT-4o-mini's flip rate fell 79% (13.3% to
  2.8%) and GPT-4.1-mini's 43% (to 7.9%), which still flipped on 7 of 29 questions, one at 50%:
  deterministic decoding reduced the inconsistency without removing it (M, arXiv 2606.13685).
- **Reasoning models may not take a temperature.** OpenAI: when reasoning effort is not `none`,
  remove `temperature`, `top_p` and `top_logprobs` (L, OpenAI latest-model guide). Anthropic:
  setting `temperature`, `top_p` or `top_k` to a non-default value returns a 400 error on Claude
  Sonnet 5 (L, Prompting Claude Sonnet 5).
- **Repeated calls are not independent.** Repeated-sample juries added little when errors were
  correlated (M, arXiv 2607.08535), and ensembles of up to 7 calls gave no significant gain in
  automated scoring (M, arXiv 2604.26954): a majority of k calls of one judge buys less than
  independence arithmetic suggests.
- **Spend repeats where they decide something.** One call by default, and three (median score,
  majority on red flags) only for cases within a point of a gate's threshold or carrying a red
  flag: if 5 to 15% of cases qualify, the total cost is 1.1 to 1.3 times one call each (inference
  and arithmetic, not measured).

## 6. When the judge changes: calibration

- **A new judge is a new measurement.** "An LLM-as-judge score can move even when the candidate
  responses stay fixed, simply because the evaluator has changed." Comparing Qwen3 dense judges
  from 1.7B to 32B parameters and adjacent MiniMax API releases (M2 to M2.7) on four judgment
  datasets, upgrades were not interchangeable: only Qwen3 1.7B to 4B gave a robust adjacent gain.
  Stronger judges reduced position and verbosity bias without removing it; juries of repeated
  samples added little when their errors were correlated; structured debate moved decisions
  substantially, but without parser and fallback logs the shifts could not be attributed to
  deliberation (M, arXiv 2607.08535). The study asks judge-based reports to include dataset
  slices, bias probes, error-dependence estimates and protocol audit trails. Re-judging with an
  updated model version "produced uniformly more lenient scores: mean gap shifts of +0.022 to
  +0.072 on HelpSteer2 and +0.031 to +0.071 on TL;DR" (P, Galileo's calibration guide, citing a
  study it links but does not name).
- **Rules that follow.** Record the judge, its version and its rubric with every result; compare
  scores only under one judge, and never chart scores from two judges on one axis; a rubric
  validated with one judge family is not validated for another; and a numeric threshold is a
  property of the judge and rubric together, so derive it again from the new judge's distribution
  when the judge changes (inference from arXiv 2607.08535).
- **A swap protocol.** Freeze a labelled set (the dev and test sizes of §1 are one floor) and
  score it with the old and the new judge. Report, per dimension, the mean shift, the ratio of
  standard deviations, rank correlation (Spearman's ρ) and chance-corrected agreement, and the
  precision and recall of red flags. A systematic offset is expected; rank preservation and
  red-flag agreement are what a gate relies on (inference). On ordinal scores plain Cohen's κ may
  over-penalise near misses: use a weighted κ or a rank correlation (P, Eugene Yan's survey);
  inspect-ai's multi-judge reliability metric computes Krippendorff's α with nominal, ordinal or
  interval levels (L, inspect-ai scoring metrics). Common readings of κ come from Landis and Koch
  (1977): 0.61 to 0.80 substantial, 0.81 to 1.00 almost perfect agreement, bands offered without
  supporting evidence (S, as summarised in the Fleiss' kappa reference). A practitioner guide warns
  that "there is no context-free kappa cutoff that makes a judge safe" and bootstraps an interval
  around κ rather than reading one number (A, OneUptime). So "κ of at least 0.6 acceptable, at
  least 0.8 aligned" is a heuristic, not a standard. Galileo's guide: "Recalibrate immediately
  after any judge model swap or vendor version bump", with weekly canary checks on fixed golden
  sets and monthly full calibration between (P).

## 7. Judging many model-drafted labels at once

Where a model assigns many items to a hierarchy (tags, categories, competencies), two published
mitigations keep its mappings traceable and structurally coherent: a supporting excerpt from the
source behind each assignment, and refinement against the hierarchy's own structure (M; Le, Abel
and Laforge, arXiv 2605.28483, abstract). A flat similarity score does not show whether an item
sits at the right level; a hierarchy-aware F1 credits structurally correct placements (M; Le and
Abel, arXiv 2510.11313, abstract). Duplicates and near-synonyms in a large model-drafted set can
show only when a reviewer reads the whole set together, not item by item (A, one uncontrolled
review).

## How to apply

1. Prefer a deterministic check wherever code can decide; use a judge for what it cannot
   ([agent-evals.md](agent-evals.md#1-suite-structure)).
2. Validate the judge against expert labels on both classes before trusting it, and report its
   true positive and true negative rates (§1).
3. Prompt a reasoning judge with the rubric and the domain facts, not with "think step by step";
   prefer binary sub-checks; ask for coverage and filter afterwards (§3).
4. Where the judge shares a family with what it scores, add a judge or a spot-check from another
   family (§2).
5. Record the judge with every result, compare only under one judge, and on a swap run the
   protocol of §6 and derive thresholds again.
6. Repeat calls only where the verdict is near a threshold, and do not count repeats of one judge
   as independent evidence (§5).
7. Treat any judge a system is optimised against as one that will be gamed (§4).

## Limits

- Most measurements are on chat and preference benchmarks (MT-Bench, JudgeBench, RewardBench,
  HelpSteer2) and on specific judge models, many now superseded; how they transfer to judging
  agent transcripts or code is not measured here.
- The effort studies disagree in shape: steady gains on JudgeBench and in automated scoring, with
  how much a level adds depending on task and model; no study read measures a judge's accuracy at
  every effort level of a current reasoning model on a rubric like yours.
- The swap protocol, the κ heuristic and the repeat budget are inference and practitioner
  guidance, not measured procedures.
- Vendor parameter rules (temperature with reasoning) are read 2026-10-01 and change with
  releases.

## Sources

All read 2026-10-01.

- Norman, Rivera and Hughes, "Reliability without Validity", arXiv 2606.19544 (2026-06-17),
  <https://arxiv.org/abs/2606.19544>.
- Yagubyan, "The Coin Flip Judge?", arXiv 2606.13685, <https://arxiv.org/abs/2606.13685>
  (abstract and HTML).
- Yang, Hou and Yang, "When the Judge Changes, So Does the Measurement", arXiv 2607.08535
  (2026-07-09), <https://arxiv.org/abs/2607.08535>.
- Spiliopoulou et al., "Play Favorites", arXiv 2508.06709 (2025-08-08),
  <https://arxiv.org/abs/2508.06709> (abstract and HTML); Wataoka, Takahashi and Ri,
  "Self-Preference Bias in LLM-as-a-Judge", arXiv 2410.21819, <https://arxiv.org/abs/2410.21819>;
  Yang et al., "Quantifying and Mitigating Self-Preference Bias of LLM Judges", arXiv 2604.22891
  (v4, 2026-06-02), <https://arxiv.org/abs/2604.22891>.
- Thakur et al., "Judging the Judges", arXiv 2406.12624 (v6, 2025-08-18),
  <https://arxiv.org/abs/2406.12624>.
- Song, Zheng and Xu, "Beyond the Illusion of Consensus", arXiv 2603.11027 (2026-03-11),
  <https://arxiv.org/abs/2603.11027>; Hong et al., "From Rubrics to Reliable Scores", arXiv
  2601.08654, <https://arxiv.org/abs/2601.08654>.
- Verga et al., "Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse
  Models" (PoLL), arXiv 2404.18796 (2024-04-29),
  <https://arxiv.org/abs/2404.18796>.
- JudgeBench, arXiv 2410.12784 (v2, 2025-04-05), <https://arxiv.org/abs/2410.12784>; Liu et al.,
  "Examining Reasoning LLMs-as-Judges in Non-Verifiable LLM Post-Training", arXiv 2603.12246
  (2026-03-12), <https://arxiv.org/abs/2603.12246>; Frohn, "The Impact of LLM Self-Consistency and
  Reasoning Effort on Automated Scoring Accuracy and Cost", arXiv 2604.26954 (2026-04-03),
  <https://arxiv.org/abs/2604.26954> (abstract).
- Fan, "Capacity, Not Format", arXiv 2606.09410 (2026-06-08), <https://arxiv.org/abs/2606.09410>.
- Shankar et al., "Who Validates the Validators?", arXiv 2404.12272,
  <https://arxiv.org/abs/2404.12272>.
- Le, Abel and Laforge, arXiv 2605.28483, <https://arxiv.org/abs/2605.28483>, and Le and Abel,
  arXiv 2510.11313, <https://arxiv.org/abs/2510.11313> (abstracts).
- Husain and Shankar, evals FAQ (modified 2026-09-21), <https://hamel.dev/blog/posts/evals-faq/>.
- Anthropic, "Demystifying evals for AI agents" (2026-01-09),
  <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>.
- OpenAI, reasoning best practices,
  <https://developers.openai.com/api/docs/guides/reasoning-best-practices>, and latest-model guide,
  <https://developers.openai.com/api/docs/guides/latest-model>.
- Anthropic, Prompting Claude Opus 4.8, Claude Sonnet 5 and Claude Opus 5,
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8>,
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5>,
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5>.
- inspect-ai, model-graded scorers, <https://inspect.aisi.org.uk/model-graded.html>, and scoring
  metrics, <https://inspect.aisi.org.uk/metrics.html>.
- Eugene Yan, "Evaluating the Effectiveness of LLM-Evaluators" (2024-08),
  <https://eugeneyan.com/writing/llm-evaluators/>.
- Galileo, "How To Calibrate LLM Judges In Production" (2026-09-28),
  <https://galileo.ai/blog/calibrate-llm-judge-human-annotations>.
- OneUptime, "How to Calibrate an LLM-as-a-Judge Against Human Labels with Cohen's Kappa"
  (2026-08-31), <https://oneuptime.com/blog/post/2026-08-31-calibrate-llm-judge-cohens-kappa/view>.
- Landis and Koch, "The measurement of observer agreement for categorical data", Biometrics 33
  (1977), bands and the note that "they supplied no evidence to support it" as given in
  <https://en.wikipedia.org/wiki/Fleiss%27_kappa>.
