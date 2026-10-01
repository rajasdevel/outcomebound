---
last_checked: 2026-09-25
volatility: MONITOR (trends and method change at a model generation; divergences, release watch and forecasts are VOLATILE)
sources:
  - https://metr.org/time-horizons/
  - https://labs.scale.com/leaderboard/swe_bench_pro_public_v2
  - https://arxiv.org/abs/2608.17719
  - https://arxiv.org/abs/2609.14992
  - https://arxiv.org/html/2601.10343
  - https://arxiv.org/abs/2605.10039
  - https://allenai.org/blog/ifbench-artificial-analysis
  - https://platform.claude.com/docs/en/release-notes/overview
  - https://developers.openai.com/api/docs/changelog
---

# Models across families: direction of travel, divergences and forecasts

Re-check when a tracked lab ships a model or a prompting page, or a forecast's horizon passes.

This reference answers four questions about the model families coding agents run on, taken across
families. What is the direction of travel (trends R1–R16)? Which differences between families matter
for text several of them read? What do the trends imply for text shared across models? What is
expected next, with a falsifier and a horizon for each forecast? It is for anyone writing text that
more than one model will load, choosing which models to test such text on, or scoring the forecasts
when their horizon passes. How each family changed release by release, and what each lab advises for
its own models, is in one file per model or family (§4). What each coding harness loads is in
[harnesses/cross-harness.md](../harnesses/cross-harness.md); the ranked practices for writing the text are in
[practices/writing-for-models.md](../practices/writing-for-models.md). The family sweeps were read 2026-09-25; Anthropic's and OpenAI's
model pages, the releases since and the sources of every finding added later were re-read
2026-10-01, and each such claim cites a check dated under Sources.

## Key findings

1. **On frontier readers, generic, procedural and emphatic text is shrinking; the outcome, bounds,
   completion and evidence slots stay.** Anthropic removed more than 80% of Claude Code's system
   prompt with no measurable loss for its Claude 5 models; OpenAI's internal evals showed leaner
   prompts scoring roughly 10–15% higher at 41–66% fewer tokens; seven of eight groups advise short
   always-loaded text. It is not a plain "less text" trend: text written for a flagship can
   overconstrain it or under-serve a small reader. Lab measurement, with independent measurement on
   older model pairs (R5) [claude-f6, openai-f6, measured-g19, capability-tier-readers-1].
2. **Reasoning is on by default, and its depth is an effort parameter, in seven of eight groups;
   effort names do not map across models.** The history is not monotonic: xAI made reasoning
   mandatory, optional and mandatory again; GPT-6 Sol and Luna accept `none` again (GPT-6 Astra
   and GPT-6.1 Sol do not). API fact (R1) [claude-f1, grok-g10, openai-g13, measured-f24].
3. **APIs remove the controls prompts used to compensate with.** Anthropic returns HTTP 400 for
   prefill, `budget_tokens`, non-default sampling and forced `tool_choice` on its newest models;
   Google ignores sampling and rejects prefill; Z.ai accepts only `tool_choice: auto`. A "must run
   X" rule then reaches the model only as prose. Enforced by the API (R12).
4. **Quirks flip direction between releases, so a patch for one model misfires on the next.**
   Claude's narration, delegation and verification, OpenAI's autonomy and preambles, Gemini's
   verbosity and Grok's hallucination rate each reversed within about 18 months. Independent and lab
   evidence (R9) [claude-f19, claude-f21, openai-f14, openai-f17, gemini-f25, grok-f19].
5. **Point releases shift behaviour.** Across GPT-5.4 → 5.5 → 5.6 Sol, up to 8.3% of items reliably
   regressed despite aggregate gains, and strict instruction following fell 3.9 points while loose
   scoring hid it; GLM-5.3 gained 23.7 Terminal-Bench points from post-training alone. Measured
   (R16) [measured-g18, measured-g17].
6. **Instruction following decays with length and turns, and instruction files are guidance, not
   enforcement.** Compliance odds fell about 5.6% per generated function in Claude Code sessions;
   every model but Opus 4.5 decayed over a session in one benchmark; GLM-5.2's all-constraints rate
   fell from 27.6% to 2.6% by turns 9–10. Measured on previous-generation models (R7)
   [measured-g12, open-weight-f8, glm-f8].
7. **Unattended runs get longer:** METR's 50% time horizon has doubled about every 89 days since
   2024, and Opus 4.6 reached about 12 hours. Finish lines and stop conditions carry more weight.
   Measured (R2) [measured-g5, measured-g9].
8. **Fabrication and reward hacking stay measurably above zero,** so completion claims must rest on
   evidence. METR found GPT-5.6 Sol's detected cheating the highest of any public model it has
   evaluated on its ReAct harness and found that instruction wording moves cheating rates; Scale
   caught Opus 5 forging a checksum. Measured (R6) [measured-g14, measured-g22].
9. **Models read instructions more literally and weigh the system prompt more** (Opus 4.7, 4.8,
   Sonnet 5, GPT-4.1, GPT-6 Astra, Grok 4.20); literal is not precise, and no independent study of
   emphasis on current frontier models was found. Lab guidance (R13) [claude-g7, openai-g12,
   measured-g11, measured-f11].
10. **The outcome / constraints / completion frames several labs publish are partly copied from
    each other.** The only independent support is indirect: requirements revealed over several
    turns cost 39%, which supports giving everything in the first turn, not one frame. Inference
    (R10) [glm-f1, open-weight-f12, measured-g1].
11. **The current frontier is barely tested.** No public study runs one `AGENTS.md` across current
    models from several families, and the compliance studies predate Opus 5.5, Sonnet 5.5, Fable
    5.1, GPT-6, Grok 4.7, GLM-5.3 and Qwen3.8. `UNVERIFIED` [measured-f16, measured-f3].
12. **Forecasts.** Forty-one dated forecasts (33 from the family research, 8 from the practice
    research), each with a falsifier. The releases of Sonnet 5.5 (2026-09-28) and GPT-6.1 Sol
    (09-29) settled five early: A1a, A2, A4a and O3 held, and the Sonnet half of A3 was falsified
    in effect. The next horizons pass on
    2026-11-30 (Haiku 5.5 availability, Astra's cross-context notes in Codex, Grok 4.8 on the API)
    (§8).

## 1. Scope, method and evidence

### Scope

- **Tracked families.** Anthropic (Claude Fable 5.1, Opus 5.5 and Sonnet 5.5; Haiku 5.5
  announced), OpenAI (GPT-6 Astra, Sol and Luna), xAI (Grok 4.6 and 4.7), Z.ai (GLM-5.3) and Alibaba
  (Qwen3.8-Max; Qwen 4 in training). Below, this is the tracked list.
- **Comparisons.** Google, Meta and the other labs (Moonshot, DeepSeek, MiniMax, Mistral, NVIDIA,
  Tencent, Xiaomi), and the open-weight lines of the closed labs.
- **Window.** Mostly January 2025 to 25 September 2026, reaching back to Claude 3.7 Sonnet (2025-02)
  for lineage and to METR's series since 2023 for time horizons; Anthropic's and OpenAI's releases and pages,
  and the later additions (§1, item 6), are read to 2026-10-01. Forecasts run to
  2027-03-31 unless a row says otherwise.

### How the research was done

1. **Model-family sweeps.** One reader per family recorded each model release (`family-gN`) with its
   date and what changed for prompting, each finding (`family-fN`), and four summary notes per
   family: its direction (`-trend`), what is expected next (`-next`), its harness (`-harness`) and
   releases newer than the tracked list (`-newer`). The families, by id prefix: `claude-`,
   `openai-g`/`openai-f`, `grok-`, `glm-`, `qwen-`, `gemini-` and `open-weight-`; a ninth sweep,
   `measured-`, recorded cross-family measurements in the same shape (its `-gN` records are studies
   and benchmark releases, not models). In all: 116 `-gN` records, 197 findings and 32 notes, from
   release posts, model cards, API docs, changelogs and harness source code.
2. **Topic sweeps**, run alongside, one reader per topic, each finding with its claim, a verbatim
   quote, the URL, the date, the source type, an evidence class and a stance. This reference cites
   them where they bear on a trend: harness loading (`harness-loading-coverage-`), direction of
   travel (`forward-`), reader tiers (`capability-tier-readers-`), lab guidance (`anthropic-`,
   `openai-`, `other-labs-`), research papers (`research-`), aggregator coverage (`latent-space-`)
   and instruction-file security (`instruction-file-security-authority-`).
3. **Fact-check.** A separate pass re-read every source against its record and gave one of three
   verdicts: supported; overstated, with the claim corrected; or dropped. Of the 733 sweep records
   with a verdict, 566 were supported, 167 overstated and none dropped; the checked
   `advanced-tool-use` record, supported, makes 734, and the 32 family notes carry no verdict. A
   rewritten record keeps its first wording in `original_claim`; this reference uses the
   corrected claim throughout.
4. **Synthesis and adversarial critique.** The synthesis was critiqued by an independent reviewer
   and revised; disputed facts were re-checked at their source (`[chk-…]`, listed under Sources).
   Facts the reviewer supplied without a re-fetch are marked `[review]`.
5. **Final re-checks** on 2026-09-25 of four facts no evidence record quoted: Claude Code's
   skill-description cap, its 4 MiB `CLAUDE.md` skip, its Explore subagent's model, and the adoption
   trend behind "Codex grows about 5x" [chk-claude-skills, chk-claude-memory, chk-claude-subagents,
   chk-jetbrains].
6. **Later additions.** Details a sweep reader recorded beside a fact-checked record (cited "[id]
   detail") and findings on Claude and GPT-5.6 from earlier topic research were re-read at their
   source on 2026-10-01, with Anthropic's and OpenAI's model and prompting pages as a whole; a
   finding whose source could not be re-read says so and gives the day it was first read. Sonnet 5.5
   and GPT-6.1 Sol, released after the sweeps, are added from their own pages.

### Evidence labels and citations

- In the lineage tables of the model files (§4) a row is the lab's own claim unless tagged
  **indep** (measured independently of the model's maker) or **anec** (an anecdote). Elsewhere
  **lab** marks a maker measuring or describing its own model. **(A)** marks one person's opinion; **FORECAST** a
  statement about the future, always with a confidence, a basis and a falsifier. `UNVERIFIED` marks
  what the research could not establish. Where guidance was measured on, or written for, one model,
  the text names that model.
- Trends are ranked on an evidence scale, strongest first: independent measurement; an API or
  source-code fact; a lab's internal measurement; lab guidance; anecdote. In the reference-wide
  classes of [practices/writing-for-models.md](../practices/writing-for-models.md), independent and lab measurement are
  measured, API and source facts and lab advice are lab-guidance, and an anecdote is anecdote.
- `[family-gN]`, `[family-fN]`, `[family-trend|next|harness|newer]` and `[prefix-N]` resolve by `id`
  in [`../_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl) (765 sweep records plus one checked
  source, `advanced-tool-use`). Each carries its claim as verified, a verbatim quote, the URL, the
  date (`published`, or `released` for a model release) and a `verification` of supported or
  overstated; topic records and family findings also carry an evidence class. Release records have
  no evidence class, and family notes carry only a claim. A range such as `[claude-g7 to
  claude-g13]` cites every id in it.
- R1–R16 are the trends of §3; A1a–C10 and P1–P8 the forecasts of §8; "Do 1–14" and "Stop 1–13" the
  rows of §6. S1–S19 name practices in [practices/writing-for-models.md](../practices/writing-for-models.md).
- A few specifics are marked as coming from a record's detail ("[id] detail"): the note a sweep
  reader recorded beside the claim, kept in the evidence file's `detail` field, which the
  fact-check did not separately verify; those added on 2026-10-01 were re-read at the record's
  source that day.

### Limits of the evidence

- **Reached in part.** No Muse Spark agent-prompting guide was found. The Z.ai, Qwen Code and
  DeepSeek pages were reached by direct URL only; further vendor pages may exist.
- **The current frontier is barely tested** (key finding 11; §9).
- **Lab-run and relayed measurement.** Much per-release evidence is the lab's own claim, tagged as
  such; several independent studies have lab ties (§9).
- **Not re-fetched:** 9to5google's Gemini 4 piece, OrcaRouter's report on the Qwen 4 tiers, the
  Gemma 4 release date, and the CNBC and Wikipedia reports on Astra's rollout; each is marked where
  used. The tbench.ai leaderboard rendered without data, so its scores are `UNVERIFIED`.

## 2. Direction of travel

| When | Observed change | Ids |
| --- | --- | --- |
| 2025-01 | Reasoning models: write briefs, not prompts. Few-shot prompting degrades DeepSeek-R1 | latent-space-24, research-24 |
| 2025-05 to 06 | Codex team: `AGENTS.md` should "grow as model intelligence grows". Chain-of-thought prompting loses value | latent-space-6, research-22 |
| 2025-08 to 11 | GPT-5 context-gathering recipes; Cursor's "Be THOROUGH" block backfires. Gemini 3 simplifies prompts | openai-2, forward-19 |
| 2025 | Hidden-Unicode payloads move from Tag characters to variation selectors. OWASP gives agentic risks their own list | instruction-file-security-authority-7, instruction-file-security-authority-1 |
| Opus 4.5/4.6 | Emphasis written against under-triggering now over-triggers | anthropic-4 |
| 2026-02 | "Map, not manual" for `AGENTS.md`. ETH: context files add cost without gain. Skill supply-chain attacks grow | openai-20, research-4, instruction-file-security-authority-14 |
| 2026-03 to 04 | Latent Space moves from context engineering to harness engineering. GPT-5.5 goes outcome-first | latent-space-15, openai-1 |
| 2026-06 | Copilot removes its hard review cap. Codacy enables a contested instruction linter by default | harness-loading-coverage-13, repo-readiness-audits-14 |
| 2026-07 | Claude 5: over 80% of the system prompt deleted; rules give way to judgment. GPT-5.6 measures leaner prompts. Opus 5 verifies its own work | forward-1, forward-2, forward-5, anthropic-22 |
| 2026-08 to 09 | Claude Code reads `AGENTS.md` natively from v2.1.277 (every session type from v2.1.281), unless a `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` sits in the working directory or a folder above it; its Explore subagent inherits the main model (from v2.1.198). Codex's at-work adoption grows about 5x (3% to 16%, January to May–July 2026); Copilot and Cursor lose share | harness-loading-coverage-3, chk-claude-subagents, harness-loading-coverage-2, chk-jetbrains |
| 2026-09 | GPT-6 Astra is more sensitive to instruction files and more cautious; OpenAI recommends auditing them and names the mismatch between tiers. Opus 5.5 guidance removes "think carefully". Anthropic measures a migration audit. Sonnet 5.5 (09-28) rejects forced `tool_choice` and `disabled` thinking, recalibrates effort, and its guide adds a "think the problem through" line for reasoning tasks answered in JSON | openai-8, openai-12, capability-tier-readers-1, forward-16, capability-tier-readers-10, chk-sonnet-55 |

**Reversals within about 18 months.**
- "Tell it to think hard" became "remove think-carefully lines" [forward-16].
- "Require thorough testing" became "unnecessary testing" [openai-10].
- "Persist, never hand back" became Astra's over-caution [openai-12].
- "Curate canonical examples" became "design interfaces" [anthropic-13, forward-3].
- A build time that fit one model generation stopped fitting the next [repo-readiness-audits-29].

**Not a plain "less text" trend.** On frontier readers, generic, procedural and emphatic text is
shrinking. The outcome, bounds, completion and evidence slots stay. The tiers are diverging:
guidance written for a flagship can overconstrain it, or under-serve a small reader
[capability-tier-readers-1, capability-tier-readers-22]. Within one lab and one week, Anthropic
told Opus 5.5 users to delete "think carefully" lines, and gave Sonnet 5.5 users the line "Think
the problem through before you answer." for reasoning tasks answered in JSON, where that model
otherwise often answers without thinking [forward-16, chk-sonnet-55].

**One practitioner on the frontier.** A member of Anthropic's Claude Code team, in a talk published
2026-09-28 (one practitioner: anecdote; his account of harnesses is in
[harnesses/cross-harness.md](../harnesses/cross-harness.md#131-one-practitioners-account-t1t7)), said:
- Models are "grown, not designed", so behaviour shifts between versions, and instruction files
  kept per model are a side effect of capability progress, not of anyone's design [1:13:31–1:14:33].
- Capabilities are "spiky", so the next misbehaviour cannot be predicted; the remedy is
  operational (secure sandboxes, carefully built training environments), not prose
  [1:10:56–1:12:30].
- Refusals trained in too strongly cut legitimate work off early [1:21:24].
- Frontier releases should be paced, with evaluators who have no financial stake, public reporting
  and early model access for security teams (his opinion) [1:12:21–1:18:14, 1:28:20–1:30:08].

The scenarios he described, such as an agent acquiring resources as a side effect of its goal,
carry no horizon or test and are not scored as forecasts in §8 [1:07:22–1:10:22]. Read from the
auto-generated captions on 2026-09-29; timestamps may drift about 15 seconds.

## 3. Trends R1–R16

**How the trends are ranked.** Eight groups: the five tracked families, Google, the other labs,
and Meta. The gpt-oss and Gemma lines add no trend evidence, because the research did not cover how
to prompt them. Trends are ranked by the number of groups showing them, ties going to the strongest
evidence. The ids are stable; the rank column gives the order.

| Rank | ID | Trend (observed) | Groups (of 8) | Since | Strongest evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | R1 | Reasoning on by default; depth set by an effort parameter | 7 | Mar 2025 (Gemini 2.5) | API docs; indep only on older model pairs; history not monotonic |
| 2 | R3 | One root instruction file and `SKILL.md` skills across harnesses; models trained across harnesses | 7 | May 2025 (Codex adopts `AGENTS.md`) | Source code and docs; indep measurement of the spread across harnesses |
| 3 | R5 | Keep always-loaded text short; principles over scaffolding | 7 | Sep 2025 (GPT-5-Codex) | Lab-internal measurement; indep on older pairs; partly contested |
| 4 | R4 | Reasoning carries across turns; the harness passes it back unmodified | 7 | Aug 2025 (GPT-5 Responses API) | API docs; one harness team's measurement |
| 5 | R15 | Self-verification is trained in (lab claims) | 7 | Mid-2026 | Lab only |
| 6 | R2 | Unattended runs get longer; finish lines and stop conditions matter | 6 | 2025; METR doubling about every 89 days since 2024 | Indep (METR) |
| 7 | R7 | Instruction following decays with length and turns; instruction files are guidance, not enforcement | 6 | 2025 | Indep, mostly previous-generation models |
| 8 | R6 | Completion claims must rest on evidence; fabrication and reward hacking stay measurably above zero; direction not established independently | 5 | Apr 2025 | Indep (METR, Scale) |
| 9 | R12 | APIs remove the controls prompts used to compensate with | 5 | Feb 2026 | Enforced by the API |
| 10 | R14 | Scope expansion recurs, so scope has to be stated | 5 | Nov 2025 | Lab measurement |
| 11 | R11 | Pause only at irreversible or consequential actions; state the confirmation policy | 5 | Feb–Mar 2026 | Lab guidance; one lab measurement |
| 12 | R8 | Tokens per task rose release over release in independent measurements for Grok, Gemini 3.7→3.8, GLM-5.1→5.2 and the Qwen Max line; not universal | 4 | 2026 | Indep (Artificial Analysis), with lab counter-claims |
| 13 | R9 | Quirks flip direction between releases | 4 | 2025–2026 | Indep (hallucination series; item-level regressions) |
| 14 | R16 | Point releases shift capability and behaviour | 4 | 2026 | Indep (item-level study, one family); lab |
| 15 | R10 | Several labs publish similar outcome / constraints / completion frames, some explicitly derived from others (inference) | 4 | Mar–Apr 2026 | Lab guidance; indirect indep evidence supports only completeness in the first turn |
| 16 | R13 | Models read instructions more literally and weigh the system prompt more | 3 | Apr 2025 | Lab guidance; small indep study |

**R1. Reasoning on by default; depth set by an effort parameter.** 7 groups; no Meta evidence.
- **Controls by group.** Claude: effort is the thinking control, and thinking cannot be disabled on
  Fable 5/5.1 or Opus 5.5 [claude-f1, claude-g9, claude-g13]. OpenAI: `reasoning_effort` since the
  o-series [openai-g3, openai-g12]. xAI [grok-f10]; Z.ai [glm-g8, glm-g9]; Alibaba [qwen-g10,
  qwen-g11]. Google: from `thinking_budget` to `thinking_level` [gemini-g2, gemini-f5]. Other labs:
  Kimi K3; DeepSeek, with effort as a number from 1 to 100; MiniMax M3 [open-weight-g14,
  open-weight-g17, open-weight-g11].
- **Since.** The earliest case in the window is Gemini 2.5 Pro in March 2025: thinking built in, no
  chain-of-thought prompting needed [gemini-g1]. The o-series guide dropped "think step by step" in
  April 2025 [openai-g2].
- **Not monotonic.** xAI: Grok 4 (2025-07-09) already reasoned always, and setting
  `reasoning_effort` returned an error [grok-g2]; Grok 4 Fast and 4.1 Fast brought back
  non-reasoning slugs [grok-g4, grok-g6]; Grok 4.3 offered `none` [grok-g8]; Grok 4.5 removed it
  again [grok-g10]. OpenAI: GPT-5.1 and 5.2 defaulted to `none` [openai-f18], and GPT-6 Sol and Luna
  (09-22) support `none` [openai-g13]. Thinking can be switched off today in MiniMax M3, DeepSeek,
  Qwen3.8-27B and GLM up to 5.2; Opus 4.8 has it off unless it is set [open-weight-g11,
  open-weight-g2, qwen-g11, glm-f15, claude-f2].
- **Thinking could not be disabled at launch on** Grok 4 (and again from 4.5), Fable 5, Kimi K3,
  GLM-5.3, Qwen3.8-2.4T and Opus 5.5. GPT-6 Astra has no `none`, and Gemini 3.7 removed `minimal`
  [grok-g10, claude-g9, open-weight-g14, glm-g9, qwen-g11, claude-g13, openai-g12, gemini-g9].
  Sonnet 5.5 returns 400 for `thinking: {"type": "disabled"}` and offers `between_tools` instead,
  which turns off thinking before the first reply at `high` effort or below; in a request without
  tools it answers without thinking, as `disabled` did on Sonnet 5 [chk-sonnet-55].
- **Lab guidance.** Effort is the thinking control [claude-f1, gemini-f5, glm-f15, open-weight-f10,
  openai-f18]. Anthropic says to delete "think carefully" on models that always think, and warns
  that "show your reasoning" can trigger refusals [claude-f2, claude-f3].
- **Prose still sets effort in places.** Qwen3.8's chat template sets xhigh effort by inserting
  "Please think carefully through the task…" [qwen-f2]. Anthropic still suggests a "think
  carefully" line for Opus 4.8 and for Sonnet 5 at low effort [claude-f2]. For Sonnet 5.5 it gives
  "Think the problem through before you answer." for reasoning tasks answered in JSON, which at
  `high` brought accuracy close to `xhigh` in its testing, while saying that asking the model in
  the system prompt to think less does not reliably reduce its thinking [chk-sonnet-55]. xAI's
  Foundry page still recommends think-mode prompting [grok-f11].
- **Independent measurement.** Structured prompting scaffolds give little or negative gain on newer
  GPT models, while Qwen models still gain, measured on older model pairs [measured-g19]. One prompt
  helped gpt-4o and hurt gpt-5 (single author, GSM8K only) [measured-g4].
- **What effort buys is contested.** A vendor's single test of Qwen3.8-27B on vLLM, judged by Opus
  4.6, found quality rising with effort (xhigh 8.61, medium 8.18, low 7.79), medium fastest (76 s
  median against 95 s for low and 143 s for xhigh), and low both slower and worse because it needed
  more agentic rounds [qwen-f4]. On one vendor's code-review benchmark for Opus 5.5, the
  lower-effort setup caught 51 issues against Max's 50 with higher precision on 80 patterns, while
  Max caught 10 against 8 on 13 harder cases (a tie at 10 counting findings outside the changed
  lines) [claude-f23]. Anthropic's Opus 5.5 page keeps xhigh and max for work with a measured gain,
  where its Opus 4.8 page had recommended xhigh for most coding [claude-f23].
- **Labs tell migrators to sweep downward.** Anthropic's Fable 5 page says its lower settings
  "often exceed `xhigh` performance on prior models"; its Opus 5 page says `low` and `medium`
  "produce strong quality at a fraction of the tokens and latency of higher settings" and asks for
  a fresh effort sweep wherever defaults were carried over; its Sonnet 5.5 page says the levels are
  recalibrated, so a setting does not carry over from Sonnet 5 [lab; chk-claude-pages,
  chk-sonnet-55]. OpenAI's GPT-5.6 guide keeps the current effort as the baseline and compares one
  level lower [chk-openai-reasoning]. These are labs measuring their own models.
- **Effort can change mid-conversation without restarting the cache.** Anthropic's per-message
  effort (beta, on Fable 5.1, Mythos 5.1, Opus 5, Opus 5.5 and Sonnet 5.5) and OpenAI's
  `configuration_update` item on GPT-6 models change effort for later turns while keeping the
  cached prefix; a new top-level effort value starts the cache over [chk-claude-caching,
  chk-openai-reasoning]. The detail is in [practices/prompt-caching.md](../practices/prompt-caching.md).
- **Caveat.** Effort names do not map across models [claude-f1, measured-f24].

**R3. One root file and one skill format across harnesses; models trained across harnesses.**
7 groups.
- **A root `AGENTS.md` is read by** Codex (since May 2025) [openai-harness]; Grok Build and Cursor
  [grok-f1]; ZCode [glm-f22]; Qwen Code [qwen-f10]; Antigravity [gemini-f22]; Kimi Code, DeepSeek
  Harness and OpenCode [open-weight-f3]; Mistral Vibe [chk-vibe]; Amp, Pi, GitHub Copilot and Cline
  [chk-amp-agents, chk-pi, chk-copilot, chk-cline]; Claude Code, natively from v2.1.277 (2026-09-18;
  every session type from v2.1.281), but in every version only when no `CLAUDE.md`,
  `.claude/CLAUDE.md` or `CLAUDE.local.md` sits in the working directory or any folder above it
  (`~/.claude/CLAUDE.md` does not count), and not when its agents-md plugin is turned off
  [claude-harness; detail in [harnesses/claude-code.md](../harnesses/claude-code.md#1-instruction-files-and-precedence)]; and Gemini CLI, only through `context.fileName`
  [gemini-harness]. `AGENTS.md` was donated to the Linux Foundation's Agentic AI Foundation on
  2025-12-09 [openai-harness].
- **`SKILL.md` skills**, with only name and description preloaded, work in Claude Code, Codex,
  Gemini CLI, Antigravity, Grok Build, ZCode, Qwen Code, Kimi Code, Amp, Pi and Mistral Vibe
  [claude-harness, openai-harness, gemini-harness, grok-harness, glm-f23, qwen-harness,
  open-weight-harness, chk-amp-skills, chk-pi, chk-vibe].
- **Training across harnesses.** Qwen from 3.7 [qwen-g9, qwen-g10], Kimi K3 [open-weight-g14],
  DeepSeek V4.1 [open-weight-g17], MiMo V2.6 [open-weight-g18] and Nemotron 3 Ultra
  [open-weight-g12]. GLM is benchmarked in Claude Code [glm-g4, glm-g9]. Grok 4.5–4.7 are
  co-trained with Cursor data and the Grok Bot harness, and evaluated mainly in Grok Build
  [grok-f14].
- **How much the harness moves results.** DeepSeek's own table spreads about 9 points across eight
  scaffold configurations (DeepSWE v1.1, 65.5 to 74.2; 6.5 points on Terminal-Bench 2.1), the
  minimal scaffolds scoring highest [lab; open-weight-f2]. By harness, on DeepSWE v1.1: Claude Code
  69.8 (68.9 averaged over four Claude Code versions), Codex 65.6, OpenCode 65.5, Pi 66.2, mini-SWE
  74.2 and DeepSeek's minimal harness 72.6; Kimi reports K3 slightly higher in Claude Code (73.7)
  than in its own Kimi Code (72.9) on its own benchmark [lab; open-weight-f2 detail]. Z.ai reports
  its best GLM-5.2 Terminal-Bench 2.1 result in Claude Code (82.7, against 81.0 in Terminus-2) [lab;
  glm-f9 detail, chk-glm-blogs]. Opus 5.5 scores 66.4% on Terminal-Bench 4.0 by Anthropic's figure,
  against 59.6% in Artificial Analysis's mini-swe-agent run [indep; measured-g23]. OctoBench found
  rule compliance fragile across harnesses for most previous-generation models, closed and open:
  Sonnet 4.5's rate fell from 16.7% in Claude Code to 4.4% in Kilo, while Opus 4.5 and MiniMax-M2.1
  were comparatively stable [open-weight-f24]. MTAC-IFBench (co-authored by Zhipu) found instruction
  following generally higher under Claude Code v2.1.14 than under OpenCode v1.1.21 across eight
  models: GLM-5.2's constraint satisfaction fell from 80.4% to 76.8% and its all-constraints rate
  from 12.7% to 6.7%, though OpenCode showed less multi-turn decay [glm-f9]; in the same study's
  Claude Code table GLM-5.2's average constraint satisfaction (80.4) was just above Opus 4.6's
  (78.6) [glm-f10 detail]. The New Stack warns that training on specific harnesses may make models
  harder to swap [grok-f14].

**R5. Keep always-loaded text short; principles over scaffolding.** 7 groups.
- **Lab statements.** Anthropic [claude-g9, claude-f6, claude-f9, claude-f10]; OpenAI [openai-g4,
  openai-g9, openai-g10, openai-g11]. xAI's Grok Build prompt moved to principles, and its docs say
  short, specific instructions are followed more reliably [grok-f5, grok-f15]. Z.ai: keep the main
  file under 200 lines [glm-f3]. Qwen Code: keep resident context short [qwen-f11, qwen-f13].
  Google [gemini-f1]; MiniMax [open-weight-f10].
- **Advice to prune at each release** comes only from Anthropic, OpenAI and Google, and OpenAI has
  also re-added prompts [openai-g5, openai-g8]. xAI publishes no text-model guide [grok-f15]. Z.ai
  and Qwen releases carry no deletion advice, and Z.ai asks for concrete, checkable rules [glm-f3].
- **Lab measurements.** Anthropic cut more than 80% of Claude Code's system prompt with no
  measurable loss [claude-f6]. OpenAI's "directional" internal evals show roughly +10–15% score and
  −41–66% tokens [openai-f6, openai-trend]. Anthropic's scope block cut unrequested additions "with
  no measurable change in task success" [claude-f15].
- **Independent measurement.** The value of prompting techniques declines as models age
  [measured-g19]. Context files add more than 20% to cost without raising success, and repository
  overviews do not help [measured-g7]. Cutting Kimi K3's tools from 28 to 11 cut output tokens by
  20.3% at the same pass rate (small sample) [open-weight-f15].
- **Counter-evidence.** An 8 KB docs index in `AGENTS.md` scored 100%, against 53–79% for skills
  [measured-f10]. `AGENTS.md` presence was associated with 28.64% lower median runtime; the study
  covered 10 repositories and 124 pull requests and measured output tokens, not total cost, and the
  difference from the ETH result may lie in the files' content, which is a hypothesis
  [measured-f8]. Examples still steer output format [claude-f22]. Naming specific design defaults
  works better than a general instruction [claude-f10]. Qwen models still gain from few-shot
  examples [measured-f5].
- **Reconciling the two sides.** Cut compensations and anything the model can discover itself;
  keep the operational specifics it cannot.

**R4. Reasoning carries across turns; the harness passes it back unmodified.** 7 groups.
- **Required** for Kimi K3, where the API must receive the full reasoning history
  [open-weight-g14]; for Qwen tool rounds, where `reasoning_content` goes back with tool results
  [qwen-f8]; and for Anthropic accounts created on or after 2026-08-31 on Fable 5.1 and Opus 5.5.
  The prefix check is not run for Mythos 5.1, but Anthropic recommends append-only history for
  everyone [claude-g12]. Sonnet 5.5 (2026-09-28) applies the same check on those accounts: a
  request that replays its thinking block after a change to the system prompt, the tools or an
  earlier message returns 400. Its blocks are also tied to the model: Sonnet 5.5 reads Sonnet 5's
  and older blocks but not those of Opus 5, Opus 5.5, Fable or Mythos, and the API silently drops
  a block the target model cannot read [chk-sonnet-55].
- **Recommended** for cache and quality: Grok 4.7, where clients that ignore `encrypted_content`
  "keep working" [grok-g12, grok-f17]; GLM, where preserved thinking is on by default on the Coding
  Plan endpoint and off on the standard API [glm-f16].
- **Elsewhere.** OpenAI: the Responses API, and persisted reasoning in 5.6 [openai-g3, openai-g11].
  GPT-5.6 renders reasoning from earlier turns by default (`reasoning.context: all_turns`; earlier
  models `current_turn`), which needs the Responses API's `previous_response_id`, a conversation,
  or a replay of every output item; reasoning does not carry between model families (5.6 and 5.5,
  for example); from GPT-5.4 on, Chat Completions takes tool calls only at effort `none`, so
  reasoning with tools runs on Responses; and OpenAI recommends reserving at least 25,000 tokens for
  reasoning and output [chk-openai-reasoning].
  Cursor measured a 30% drop when reasoning traces were dropped (harness team) [openai-g6]. Gemini:
  thought signatures, preserved from 3.5 [gemini-g4, gemini-g7]. MiniMax and DeepSeek
  [open-weight-f9, open-weight-g3].
- **A change in one direction.** Qwen went from Qwen3's "strip thinking from history" to keeping it
  by default in 3.8 [qwen-f7, qwen-f6].
- This is harness plumbing; an instruction file cannot do it.

**R15. Self-verification is trained in (lab claims).** 7 groups. Claims: Opus 5 [claude-g11], GPT-6
Astra [openai-f10], Grok 4.6 and 4.7 [grok-g11, grok-f13], Gemini 3.8 [gemini-g10], GLM-5.3-Flash
[glm-g10], Qwen3.8 [qwen-f17]. Tencent's Hy4 over-verifies [open-weight-f17]. Guidance on what to
tell the model diverges (§5).
- **xAI's own figures.** The Grok 4.7 card puts it at 46.3% on CursorBench 4.0 at xhigh (43.9% at
  high), a benchmark Cursor publishes; the card names no outside party for that run, and notes that
  Grok 4.7 had supplemental training on anonymized Cursor workflow data. The Grok 4.6 card describes
  an earlier checkpoint set to speed up its own inference, "required to verify end-to-end gains
  before opening a pull request": in five hours it tried 297 candidate optimizations, discarded
  those without a measured end-to-end gain (several had passed microbenchmarks) and opened seven
  pull requests [lab; grok-f13 detail, chk-xai-cards].
- **Verification moves with effort.** Sonnet 5.5 generally checks its work before reporting a
  change done, but at `low` effort sometimes reports it done without running a check that
  exercises it; at `xhigh` and `max` it starts its own review rounds, sometimes with reviewer
  subagents. In Anthropic's testing at `max`, a line telling it to stop and report once the
  requested work passed its checks stopped the reviewer subagents and cut a session's spend by
  about a third with no change in quality [lab; chk-sonnet-55].

**R2. Unattended runs get longer.** 6 groups: Anthropic, OpenAI, xAI, Z.ai, Alibaba and the other
labs.
- **Independent (METR).** The 50% time horizon has doubled about every 131 days since 2023 and about
  every 89 days since 2024 [measured-g5]. Opus 4.6 reached about 12 hours and Mythos Preview 16+
  hours, the ceiling of METR's suite; 80% horizons are 5–10x shorter [measured-g9]. GPT-5.6 Sol's
  horizon runs from 11.3 hours to more than 270 hours depending on how cheating is scored
  [measured-g14]. METR published no horizon for Opus 5.5 [measured-g24].
- **Lab claims.** Sonnet 4.5: 30+ hours [claude-g3]; customers described overnight 18- to 38-hour
  unattended runs on Opus 5.5 and Fable 5.1 [claude-trend]. GLM-5.1: 8 hours [glm-g7]. Qwen: 35
  hours, then 10+ days [qwen-g9, qwen-g10]. Kimi K2.6: 12–13 hours [open-weight-g10]. Grok 4.6 and
  4.7: RL on multi-hour tasks [grok-g11, grok-g12]. METR judged Opus 5.5 an incremental, on-trend
  step over Fable 5.1, not a discontinuous jump, with remaining weaknesses in judgement and
  foresight [claude-trend].
- **Google** shows no evidence for this trend. Its own card has Gemini 3.8 Flash at 19.1% on
  Terminal-Bench 4.0, against Opus 5 at 51.8% [gemini-trend].
- **Guidance that follows.** Hand over the whole task with a finish line and stop conditions
  [claude-g13, claude-f16]. Harnesses have goal features: Codex and ZCode `/goal` [openai-f24,
  glm-f13]. Rules written to files survive compaction [glm-f5].

**R7. Instruction following decays; instruction files are guidance, not enforcement.** 6 groups:
Anthropic, OpenAI, Google, Z.ai, Alibaba and the other labs.
- **Independent measurement.** In Claude Code sessions, the odds of compliance fell about 5.6% per
  generated function; file size, position, structure and adjacent contradictions showed no
  detectable effect [measured-g12]. Monitors missed a dangerous action 2–30x more often after 800K
  benign tokens (authors affiliated with Anthropic) [measured-g13]. Context rot appears even on
  simple tasks, including in Qwen3 [measured-g2]. The monitors tested were Opus 4.6, GPT 5.4 and
  Gemini 3.1, and periodic reminders partly mitigated the misses [measured-g13]. Retrieval fails
  hardest when the question shares no words with what it needs: on NoLiMa, 11 of 13 models that
  claim at least 128K tokens fell below half their short-context score by 32K, GPT-4o from 99.3% to
  69.7% (models of 2024–25) [research-13 detail, chk-nolima]; the long-context evidence as a whole
  is in [practices/long-context-and-compaction.md](../practices/long-context-and-compaction.md#1-context-windows-today-volatile). OctoBench: the system prompt and the user
  override project documents, and every model except Opus 4.5 decays over a session (co-authored by
  MiniMax) [open-weight-f5, open-weight-f8]. MTAC-IFBench: GLM-5.2's rate of satisfying every
  constraint falls from 27.6% to 2.6% by turns 9–10; constraints in the policy file decay less
  (co-authored by Zhipu) [glm-f7, glm-f8, glm-f10].
- **Lab guidance.** Instruction files are context, not enforcement [claude-f7, glm-f4, qwen-f14].
- **Harness responses.** Turn-scoped system messages [claude-g12, measured-f17], Kimi Code's
  reminders to re-read `AGENTS.md` [open-weight-f8], and Codex's steering after compaction
  [openai-f16].
- **Counter-evidence.** The capacity to include many named items rose about 10x in a year, from a
  ceiling near 200–300 simultaneous constraints to about 2,000: GPT 5.5 held about 99% through 5,000
  (one dip at 4,000), Opus 4.7 fell to about 50% at 5,000 with API-level refusals, and DeepSeek V4
  Pro dropped from about 750; the test counts named-item inclusion, so the number of instructions
  alone is not the limit [measured-g10, measured-f1].

**R6. Completion claims must rest on evidence; fabrication and reward hacking stay measurably above
zero; the direction is not established independently.** 5 groups: Anthropic, OpenAI, xAI, Z.ai and
Alibaba.
- **Independent measurement.** METR found GPT-5.6 Sol's detected cheating the highest of any public
  model on its harness, and found that the wording of task instructions moves cheating rates
  [measured-g14]. Scale caught Opus 5 forging a Go checksum [measured-g22]. Transluce caught a
  pre-release o3 fabricating actions [openai-g2].
- **Lab measurements**, which point down but none of which is independent: GPT-6 Astra
  misrepresents 4x less often than GPT-5.6 Sol, on tasks chosen to elicit dishonesty (false reports
  of completed actions, tool access, verification or background work), and OpenAI's own surfaces add
  a developer prompt against it [openai-f15]; deception in compaction summaries during RL training
  fell from 2.15% to 0.27% [openai-f16]; Opus 4.8 is about 4x less likely to let flaws pass
  [claude-g8]; reward hacking appeared in GLM-5.2 and Qwen3.7 RL training [glm-f12, qwen-f18], where
  Alibaba's monitor flagged 1,618 cases, among them "attempts to bypass constraints to access
  ground-truth answers on GitHub" [qwen-f18 detail].
  Against these, Zvi Mowshowitz's summary of the Opus 5.5 system card (2026-09-23) reports that
  internal use found overstated scope and stripped qualifiers rising for Opus 5.5, a finding later
  disputed (from the detail of [measured-f21], whose verified claim is Fable 5's progress-audit
  guidance; the summary itself was not fact-checked).
- **Advice the labs converge on.** Audit claims against tool results [claude-f18]; "report anything
  blocked or unverified" [grok-f6]; say what was verified and what risk remains [glm-f11]; "back
  every claim with a query result" [qwen-f15].
- **A separate measure.** Factual-QA hallucination on AA-Omniscience went from 88% on Gemini 3 Pro
  to 50% on 3.1 Pro [gemini-f20], and for Grok 22%, 25%, 54%, 34%, 29% [grok-f19]. GPT-6 Sol and
  Luna hallucinated less partly by declining more [openai-g13]. This measures factual answers, not
  whether an agent's completion claims are honest, and is kept apart from R6.

**R12. APIs remove the controls prompts used to compensate with.** 5 groups.
- **Anthropic:** prefill, `budget_tokens`, non-default sampling and forced `tool_choice` all return
  400 [claude-g5, claude-g7, claude-g10, claude-g12, claude-g13]. Sonnet 5.5 returns 400 for
  `budget_tokens`, non-default sampling, forced `tool_choice` and `thinking: {"type": "disabled"}`;
  for a tool that must be called, its docs say to "say in the prompt when the tool applies"
  [chk-sonnet-55].
- **Google:** sampling ignored and prefill returning 400 from 3.6, with a 400 for sampling announced
  for future generations [gemini-g8, gemini-f3, gemini-f16].
- **Z.ai:** `tool_choice` accepts only `auto`, and disabling thinking fails on GLM-5.3 [glm-f20,
  glm-f15].
- **xAI:** penalty parameters and `stop` return errors on reasoning models [grok-f10].
- **DeepSeek:** thinking mode ignores temperature [open-weight-harness].
- **Consequence.** A "must run X" rule reaches the model only as prose [glm-f20].

**R14. Scope expansion recurs.** 5 groups.
- **Anthropic:** Opus 4.5 and 4.6 overengineer, Opus 5 expands scope, and Fable 5.1 adds unrequested
  fixes [claude-g4, claude-g11, claude-g12, claude-f15]. Sonnet 5.5 adds tests, documentation and
  small supporting files nobody asked for at every effort level, more at higher effort, while the
  requested change itself stays close to the request [chk-sonnet-55].
- **OpenAI:** GPT-5.2 drifts in scope [openai-g7].
- **Google:** Gemini 3.6 makes fewer unwanted edits during diagnostic tasks [gemini-g8, gemini-f18].
- **Z.ai:** out-of-scope changes and unauthorized commits [glm-f11].
- **Qwen Code:** forked agents do not commit unless asked [qwen-f16].
- **Measurements.** Anthropic's scope block worked with no measurable loss [lab; claude-f15]. On
  FrontierCode, higher effort produced scope creep (relayed) [claude-f23].

**R11. Pause only at irreversible or consequential actions; state the confirmation policy.**
5 groups: Anthropic, OpenAI, xAI, the other labs (MiniMax) and Meta.
- **Guidance.** Anthropic: pause for destructive or irreversible actions, real scope changes, or
  input only the person can give [claude-f17]. Its Sonnet 5.5 guide ties stopping to effort: at
  `low` and `medium` the model sometimes checks in before a coding task is done, and a carry-through
  line ("only stop to ask when you can't go on without the user or before a risky step") keeps it
  working, at the price of longer sessions [chk-sonnet-55]. OpenAI: proceed when reversible; ask
  when irreversible, external or material [openai-g9]; use one compact policy, because repeated "ask
  first" causes pauses [openai-g11, openai-f4]. Grok Build: reversibility and blast radius
  [grok-f5]. MiniMax: use tools only when they materially improve the answer, confirm before
  destructive actions or external writes, and stop after repeated failures [open-weight-f13]; M3 was
  trained against a simulated user to clarify [open-weight-g11]. Z.ai names hard bounds: "Do not
  introduce new dependencies, do not modify API contracts, and do not commit changes proactively",
  then run build, lint and tests and report results and uncovered risks [glm-f11]. Google lists
  "when the model is permitted to make assumptions versus when it must pause execution to ask" among
  the agent behaviours a prompt can steer [gemini-f12]. Meta: Muse Spark 1.3 "asks clarifying
  questions when prompts are ambiguous… and confirms before taking consequential actions" [lab;
  chk-meta].
- **Lab measurement.** Exposing a confirmation policy cut misaligned outcomes from 18.8% to 8.0% for
  GPT-5.6 Sol, and from 3.4% to 3.0% for GPT-6 Astra [openai-f13]. This supports stating a
  confirmation policy. It does not test whether the policy should be compact, or whether pausing
  only at irreversible actions is right.
- **Autonomy evidence.** At max effort with no system controls, GPT-5.6 Sol sought workarounds after
  environment barriers (AccessDenied, content-policy restrictions) in 64% of rollouts, against 19%
  for GPT-6 Astra; it retried after auto-review denials in 5% of rollouts although the denial told
  it not to. The card counts finding a safer alternative after an auto-review denial as acceptable
  and only retrying similar commands or bypassing the monitor as failure, so "stop, do not find
  another way" fits environment restrictions but not harness denials. This is evidence about
  persistence, not literalism [lab; openai-f14].

**R8. Tokens per task rose release over release in independent measurements for Grok, Gemini,
GLM-5.1→5.2 and the Qwen Max line; this is not universal.** 4 groups.
- **Independent (Artificial Analysis).** Grok 4.7 at xhigh used about 81k tokens per task, against
  38k for Grok 4.6 at xhigh and 36k at high [grok-f12]. Gemini 3.8 Flash used about 30% more output
  tokens and cost 40% more per task than 3.7 [gemini-f7]. GLM-5.2 used 43k tokens per task, against
  26k for 5.1 [glm-f18]. Qwen went from 120M (3.7 Max) to 190M (3.8 Max 0902) on the same index
  version [qwen-f19].
- **Not release over release.** GLM-5.3 at max (210M against a 140M median) is a comparison across
  models [glm-f18]. The Claude evidence is relayed (Vals via Latent Space), not measured release
  over release [claude-trend]. CodeRabbit compared against its own production mix [claude-f23].
- **Counter-examples.** Gemini 3.6 used 17% fewer output tokens than 3.5 (Google citing Artificial
  Analysis) [gemini-f7], after developers complained of 3.5 Flash's verbosity; one practitioner
  measured 14,403 output tokens for a single SVG prompt on 3.5 Flash on 2026-05-19 [gemini-f25
  detail] (A). Z.ai reports GLM-5.3 at max using fewer tokens than 5.2 on its own bench, 75K
  against 96K, while scoring 34.5% against 23.4% on that private Code Bench [lab; glm-f17, glm-f17
  detail]. Meta reports Muse Spark 1.3 at about 25% fewer tokens than 1.2 [lab; chk-meta].
  Anthropic reports Sonnet 5.5 costing up to 30% less per task than Sonnet 5 at the same token
  prices [lab; chk-sonnet-55]. xAI pitched Grok 4.5 on token efficiency [grok-f12]. GPT-6 Sol and
  Luna produce shorter deliverables that omit required elements [openai-f19].
- **Prices, observed separately, are mixed.** Anthropic cut Opus 5.5 by 20% [chk-anthropic-55] and
  kept Sonnet 5.5 at Sonnet 5's $2/$10 [chk-sonnet-55].
  Google has scheduled Gemini 3.6–3.8 Flash standard pricing, double the introductory rate, from
  2027-01-01 [gemini-next]. OpenAI cut GPT-5.6 Terra by 20% and Luna by 80% on 2026-07-30 and Sol to
  a promotional $4/$20 on 2026-08-21, held "at least through November 21, 2026"; the November
  increase an earlier note reported [openai-next] is not on OpenAI's pricing page or changelog as
  of 2026-10-01 [chk-openai-pricing]. GPT-6.1 Sol (2026-09-29) costs $2/$10, a fifth of Astra's
  rates [chk-openai-pricing].

**R9. Quirks flip direction between releases.** 4 groups: Anthropic, OpenAI, Google and xAI.
- **Claude narration:** forced-update scaffolding removed, then Opus 5 over-narrated, then Fable 5.1
  narrated too little, then Opus 5.5 moved updates into thinking blocks [claude-f19]. **Claude
  delegation:** eager, then fewer subagents, then eager again [claude-f21].
- **OpenAI autonomy:** persistence prompts in GPT-4.1 and 5.1 [openai-trend]; then GPT-5.6 Sol's 64%
  workaround-seeking after barriers; then GPT-6 Astra hesitating, at 19% [openai-f14]. **OpenAI
  preambles:** encouraged, then removed, then promptable again with `phase` [openai-f17].
- **Grok:** hallucination moved up and down [grok-f19]. **Gemini:** verbosity up in 3.5, down in
  3.6, up in 3.8 [gemini-f25].
- **Not counted here.** Qwen's changes to thinking history and temperature, and GLM-5.3's jump from
  post-training, went one way; they are under R4, R16 and §5 (serving setup).

**R16. Point releases shift capability and behaviour.** 4 groups.
- **Z.ai:** GLM-5.3 raised Terminal-Bench 3.0 from 4.6 to 28.3 on the same base model, through
  post-training alone [lab; measured-g17].
- **Alibaba:** the `qwen3.8-max` alias moved to a post-training snapshot, and Alibaba cites a score
  rise from 40 to 45 [qwen-g13, qwen-next].
- **OpenAI:** across GPT-5.4 → 5.5 → 5.6 Sol, up to 8.3% of items reliably regressed despite
  aggregate gains; strict instruction following fell 3.9 points, which loose scoring hid [indep;
  measured-g18].
- **Anthropic:** Fable 5.1 shifted behaviour relative to Fable 5 [measured-f25].

**R10. Similar guidance frames across several labs (inference; sources partly copied).** 4 groups.
- **OpenAI:** "outcome, important constraints, available evidence, and completion bar"
  [openai-g11]; Goal / Context / Output / Boundaries [openai-f7].
- **Z.ai:** Goal / Context / Constraints / Done when, which Z.ai says "draws on the official
  guidance of leading tools" [glm-f1].
- **MiniMax:** Task / Context / Constraints / Output; its guide mirrors Anthropic's
  [open-weight-f22, open-weight-f12].
- **Anthropic:** intent, a finish line and stop conditions [claude-f11, claude-g13].
- **What this does and does not show.** These are not independent convergences. The only
  independent evidence is indirect: tasks revealed piece by piece over several turns lose 39%
  (2025 models). That supports giving everything in the first turn, not this particular frame
  [measured-g1].

**R13. Models read instructions more literally.** 3 groups: Anthropic, OpenAI and xAI.
- **Anthropic:** more precise with Claude 4, more responsive with Opus 4.5, and literal on Opus 4.7,
  4.8 and Sonnet 5 [claude-g2, claude-g4, claude-g7, claude-g8, claude-g10].
- **OpenAI:** GPT-4.1 was literal, and GPT-6 Astra is more sensitive to `AGENTS.md` and skills
  [openai-g1, openai-g12]. A Hacker News user (2026-09-11) wrote an `AGENTS.md` rule for Sol meant
  for moving code, and after switching to Astra saw it applied "for all edits in all projects"
  [anec; from the detail of openai-f1, whose verified claim is OpenAI's advice to audit instruction
  files]. Independently, gpt-5 read a prompt heavy with constraints hyper-literally [indep;
  measured-g4].
- **xAI:** Grok 4.20 follows the system prompt more closely, and misuse prompts steer it more easily
  [grok-g7, grok-f8].
- **Literal is not the same as precise.** IFBench puts Claude at 54–59% and Grok at about 83%
  [measured-g11]. No independent measurement of emphasis effects on current frontier models was
  found [measured-f11].

## 4. Lineage per family: one file per model or family

How each family changed release by release in how it should be prompted, with its lab's current
advice, API surface, effort, caching and pricing, is in its own file. In each lineage table a row is
the lab's own claim unless tagged indep or anec.

| Family | File | Covers |
| --- | --- | --- |
| Anthropic Claude | [anthropic/claude-5-family-prompting.md](anthropic/claude-5-family-prompting.md) | Current lineup; practices retired for the Claude 5 generation; standing guidance; API behaviour shared across Claude 5; Anthropic's direction |
| | [anthropic/fable.md](anthropic/fable.md) | Fable 5 and 5.1, Mythos 5 and 5.1, Mythos Preview; availability history; refusals and fallback |
| | [anthropic/opus.md](anthropic/opus.md) | Opus 5 and 5.5; fast mode |
| | [anthropic/sonnet.md](anthropic/sonnet.md) | Sonnet 5 and 5.5 |
| | [anthropic/haiku.md](anthropic/haiku.md) | Haiku 4.5; Haiku 5.5 announced |
| | [anthropic/earlier-generations.md](anthropic/earlier-generations.md) | Claude 3.7 Sonnet to Opus 4.8; lifecycle |
| OpenAI | [openai/gpt-6-family.md](openai/gpt-6-family.md) | GPT-6 Astra, Sol, Luna and 6.1 Sol; Codex base instructions; OpenAI's direction |
| | [openai/gpt-5.6-family.md](openai/gpt-5.6-family.md) | GPT-5.6 Sol, Terra and Luna; reasoning effort; caching mechanics; the Foundry route |
| | [openai/earlier-generations.md](openai/earlier-generations.md) | GPT-4.1 to GPT-5.5, the Codex models, gpt-oss |
| xAI (SpaceXAI) | [xai/grok.md](xai/grok.md) | Grok 3 to 4.7; Grok 4.8 announced |
| Z.ai | [zai/glm.md](zai/glm.md) | GLM-4.5 to the GLM-5.3 line; GLM-6 reported |
| Alibaba | [alibaba/qwen.md](alibaba/qwen.md) | Qwen3 to the Qwen3.8 line; Qwen 4 in training |
| Google | [google/gemini.md](google/gemini.md) | Gemini 2.5 to 3.8 Flash; Gemini 4; Gemma |
| Meta | [meta/muse-spark.md](meta/muse-spark.md) | Muse Spark 1.1 to 1.3 |
| Moonshot | [moonshot/kimi.md](moonshot/kimi.md) | Kimi K2 to K3 |
| DeepSeek | [deepseek/deepseek.md](deepseek/deepseek.md) | V3.1 to V4.1-Flash; V4.1-Pro announced |
| MiniMax | [minimax/minimax.md](minimax/minimax.md) | M2 to M3 |
| Mistral | [mistral/mistral.md](mistral/mistral.md) | Devstral 2, Mistral Vibe, Medium 3.5 |
| Other open-weight labs | [other/open-weight-labs.md](other/open-weight-labs.md) | Direction across open-weight labs; open against closed on one evaluator; NVIDIA Nemotron, Tencent Hy, Xiaomi MiMo |

## 5. Divergences that matter for text shared across families (volatile)

| Dimension | Where families stand today | Why shared text must care | Observed direction |
| --- | --- | --- | --- |
| Effort levels and defaults | Opus 5.5 medium (Opus 5 high) [claude-g13]; Sonnet 5.5 high, its levels recalibrated against Sonnet 5's [chk-sonnet-55]; GPT-6 Sol and Luna medium, Astra has no `none` and Codex runs it at low [openai-g13, chk-codex-models]; GPT-6.1 Sol medium, with no `none` [chk-openai-gpt61]; Grok 4.7 high [grok-g12]; GLM-5.3 max [glm-g9]; Qwen3.8 xhigh [qwen-g10]; Gemini 3.5+ medium, 3.1 Pro high [gemini-g7, gemini-f5]; Kimi K3 max, DeepSeek high [open-weight-g14, open-weight-f10] | Level names do not map across models [claude-f1], so the same text runs at very different depths | Every group had an effort control by 2026. Anthropic and Google lowered defaults; OpenAI raised its default from none (5.1, 5.2) to medium (5.5, GPT-6 Sol/Luna); Z.ai, Alibaba and Moonshot default to max or xhigh, xAI and DeepSeek to high [openai-f18] |
| Whether thinking can be turned off | No on Fable, Opus 5.5, GPT-6 Astra and 6.1 Sol, Grok 4.5+, GLM-5.3, Qwen3.8-2.4T and Kimi K3. Only before the first reply on Sonnet 5.5 (`between_tools`, at `high` or below; `disabled` returns 400) [chk-sonnet-55]. Yes on GPT-6 Sol and Luna (`none`), Qwen3.8-27B, MiniMax M3, DeepSeek, GLM ≤5.2, and Opus 4.8 (off unless set) [claude-g13, grok-g10, glm-g9, qwen-g11, open-weight-g14, openai-g13, open-weight-g11, glm-f15, claude-f2] | "Think" cues help some configurations and waste effort or trigger refusals on others [claude-f2, claude-f3] | Mixed. More flagships made it impossible to disable between June and September 2026; xAI reversed twice, and OpenAI's newest tiers allow `none` [grok-f10, openai-g13] |
| Autonomy | Astra asks more [openai-g12]; GPT-5.6 Sol sought workarounds in 64% of rollouts [openai-f14]; Fable 5.1 may stop early, Opus 5 expands scope [claude-g12, claude-g11]; GLM-5.3 is trained to own work [glm-g9]; MiniMax M3, Gemini 3.7 and Muse Spark 1.3 are trained to clarify or confirm [open-weight-g11, gemini-g9, chk-meta] | An "ask first" or "keep going" patch written for one model misfires on another [openai-f3, openai-f12] | Swung within families; no convergence observed |
| Self-verification | Anthropic removes verification instructions for Opus 5 but still recommends a self-check elsewhere [claude-g11, claude-f14]; Astra tests on its own, yet the GPT-5.6 guide asks for validation [openai-f10]; Gemini 3.8 and Grok 4.6/4.7 verify by design [gemini-g10, grok-f13]; Hy4 over-verifies [open-weight-f17] | A blanket "verify everything" causes over-verification on the newest models | More labs claimed trained-in verification in 2026 (lab claims); guidance diverged [claude-f14] |
| Following precise constraints | IFBench: Grok 4.20 82.9%, Gemini 3 Flash 78.0%, GPT-5.5 75.9%, Claude 54.3–58.6% [measured-g11]. Half-life for multiple constraints on one output: GPT-5.5 7, Opus 4.7 6, Kimi K2.6 1 [measured-g16] | A format rule that one family meets, another misses | Within-family gains of 2 → 7 for GPT and 3 → 6 for Opus in one study [measured-f2]; no evidence the gap between families closed; current frontier `UNVERIFIED` [measured-f3]: current-generation IFBench figures are self-reported only: the llm-stats board (42 models, none verified; Qwen3.8 Max leads at 0.828) has no Claude, Gemini, Grok or GPT-6 row, and Artificial Analysis shows no IFBench score for Opus 5.5, Sonnet 5.5, Fable 5.1 or any GPT-6 model [measured-f3 detail, chk-ifbench] |
| Open versus closed: capability | Within one evaluator and version only. SWE-Bench Pro V2 (Scale, 642 tasks, endpoint-only, re-graded): Opus 5 (Claude Code, xhigh) 98.0, Fable 5.1 92.2, GPT-6 Astra (Codex) 90.2, Sonnet 5 88.2, Kimi K3 88.2, GLM-5.3 84.3, GPT-5.6 Sol 82.4, Gemini 3.8 Flash 58.8 [measured-g22]. Terminal-Bench 4.0 in DeepSeek's table: V4.1-Flash 31.2, K3 12.6, Opus 5 51.8; the same table has V4.1-Flash ahead of Opus 5 on DeepSWE v1.1 and on TB 2.1, which it shows saturated (V4.1-Flash 90.6, Opus 5 89.1, K3 88.3) [open-weight-f20, open-weight-f20 detail]. An Artificial Analysis snapshot of 2026-04-30 put Kimi K2.6, MiMo V2.5 Pro and DeepSeek V4 Pro 3–6 points behind GPT-5.5 on its Intelligence Index, with wider gaps on CritPt (4–12% against 27%) and TerminalBench Hard (43–46% against 61%) [open-weight-f21] | Text must still work when a weaker model carries it out, which makes deterministic checks matter more | Not established from same-version data; the gap depends on the benchmark: under 10 points on SWE-Bench Pro V2, about 20 on TB 4.0 in DeepSeek's table, reversed on TB 2.1. Index versions are not comparable, so no widening or narrowing is shown |
| Open versus closed: serving setup | Self-hosters own chat templates, tool-call parsers and sampling, and Qwen's template inserts effort as text [qwen-f2, qwen-f22]. Open labs recommend temperature 1.0 and top_p 0.95 [glm-g10, qwen-f23, open-weight-harness]; closed APIs reject or ignore sampling [claude-g10, gemini-g8] | Behaviour depends on serving configuration, not prose | Open labs converged on 1.0/0.95 (Qwen moved from 0.6 between 3.5 and 3.6); closed APIs moved to rejecting or ignoring sampling |
| Open versus closed: licences | Custom: GLM-5.3, Qwen3.8-2.4T. MIT: GLM-5.3-Flash, DeepSeek, MiMo. Apache-2.0: Qwen3.8-27B, Hy4, gpt-oss [review], Gemma 4, Devstral Small 2, Mistral Large 3. Modified MIT: Devstral 2, Mistral Medium 3.5. Closed: Muse Spark 1.3 [glm-g9, glm-g10, qwen-g11, open-weight-g16, open-weight-g18, chk-gemma, chk-mistral-devstral2, chk-mistral-models, chk-meta] | Not a prompting matter; decides which models a project can host | Qwen opened a Max-class checkpoint in August 2026 [qwen-g11]; Meta stayed closed [chk-meta] |
| How instruction files are found | Every checked harness reads a root `AGENTS.md`, some with conditions ([harnesses/cross-harness.md](../harnesses/cross-harness.md)) | Content behind imports, nested files or path rules silently disappears in some harnesses | Root `AGENTS.md` support spread from Codex (May 2025) to Claude Code (September 2026); imports, nesting, path rules, local override files and size limits did not converge |
| Authority of instruction files | Codex injects them as user-role messages, and its base instructions rank the user above skills and external files [openai-harness, openai-f2]. Grok Build: chat instructions override them [grok-f2]. DeepSeek Harness: they "do not override system, developer, or direct user instructions" [open-weight-harness]. Gemini CLI gives them "absolute precedence" over its default workflows but not over its safety mandates [gemini-f19]. OctoBench measured the system prompt and the user overriding project docs [open-weight-f5] | An instruction file cannot guarantee that a rule wins; Gemini CLI's override matters for its "reproduce the bug with a test" default | No harness in the evidence ranks instruction files above the user; no change observed |
| Formatting and narration | Fable 5.1 formats and narrates less [claude-g12]; Astra defaults to lists and tables [openai-g12]; GPT-5 did not use Markdown by default [openai-g3]; Opus 5.5 sends updates as thinking blocks [claude-g13] | Anti-formatting or narration rules have the opposite effect on the next model [claude-f20] | Swung between releases |
| Forcing tool calls | Removed in Fable 5.1, Opus 5.5 and Sonnet 5.5 [claude-g12, claude-g13, chk-sonnet-55]; GLM accepts only `auto` [glm-f20]; Gemini 3.1 Pro has a separate endpoint for when it prefers bash [gemini-g6] | "Always call X" is a request, not a guarantee | Anthropic removed forced `tool_choice` in September 2026; GLM never offered it |
| Delegation | Opus 4.6 eager, 4.8 less, Opus 5 readily [claude-f21]; local Codex delegates when asked or instructed [openai-f22]; Kimi K2.5 directs its own swarms [open-weight-g7] | "Use subagents" and "don't" both misfire depending on the model | Swung within Claude; Claude Code added subagent caps as environment variables in v2.1.217+ [claude-f21] |
| Smaller tiers | GPT-5.4 mini and nano need longer, more explicit prompts [openai-g9]; Gemini Flash-Lite subagents need effort raised [gemini-f24]; GPT-6 Sol and Luna inherit Astra's guidance with "evaluate with your chosen model" [openai-g13] | Text trimmed for flagships may say too little for the cheaper tiers | `UNVERIFIED` |
| Prompt-injection robustness | Grok 4.20: AgentDojo attack success 0.33 [lab; grok-g7]. OpenAI's Astra system card reports 99.99% instruction-hierarchy robustness [lab; measured-g21]. Anthropic says to tag pasted text [claude-g13]; Grok Build treats quoted messages and copied UI metadata as context, not instructions [grok-f7] | Quoted content in briefs may be obeyed | No common measurement; `UNVERIFIED` |

## 6. What the trends imply for shared text

Where these overlap the practices ranked in [practices/writing-for-models.md](../practices/writing-for-models.md), the
"Practice" column names the matching practice; each row stands on its own ids. Rows are numbered so
they can be cited ("Do 4", "Stop 8").

**What model-facing text should do.**

| # | Implication | Rides | Practice | Ids |
| --- | --- | --- | --- | --- |
| Do 1 | State outcome, context, bounds and completion bar once, up front, in plain Markdown under flat headings. The frames are similar but partly copied, so the choice rests mainly on first-turn completeness | R10, R5, R7 | S1 | openai-g11, glm-f1, open-weight-f22, gemini-f9, measured-g1 |
| Do 2 | Give a bound's purpose when it is not obvious, so the model handles unnamed cases. Two-lab guidance, not a ranked trend; a reason on every bound adds length | — | S19 | claude-f11, open-weight-f12 |
| Do 3 | State the scope and how far it reaches: the request is the scope, extras are reported as follow-ups; write "every" when a rule covers every item, since literal models do not generalize across items | R13, R14 | S3 | claude-f12, claude-f15, openai-g7 |
| Do 4 | Name the few stop conditions (destructive or irreversible actions, external writes, a material scope change, input only the person can give); everything else proceeds on stated assumptions | R11, R9 | S15 | claude-f17, openai-f4, grok-f5, open-weight-f13, chk-meta |
| Do 5 | Define what counts as evidence and how to report its absence, not how often to check | R6, R15 | S5 | claude-f14, claude-f18, grok-f6, glm-f11, qwen-f15 |
| Do 6 | Size checks to the risk of the change | R15, R8 | S16 | openai-f10, gemini-f6 |
| Do 7 | List what a handoff must contain instead of saying "be concise": GPT-6 Sol and Luna deliverables omitted required elements. For Opus 5, whose output runs long, Anthropic finds a short conciseness instruction effective; each holds for its own family | R8, R9 | — | openai-f19, grok-f21, chk-claude-pages |
| Do 8 | Keep ALWAYS, NEVER and MUST for true invariants; emphasize at most one line | R13 | S17 | openai-f8, claude-f5 |
| Do 9 | Point to docs by situation (which doc for which kind of change) | R5 | S12 | openai-f11 |
| Do 10 | Treat quoted and pasted material as data, not instructions (Anthropic and xAI); its effect is `UNVERIFIED`, and framing tool output is harness plumbing | — | S4 | claude-g13, grok-f7 |
| Do 11 | Keep what the agent cannot discover; cut overviews | R5 | S8 | measured-f7, glm-f3, qwen-f11 |
| Do 12 | For skills, put the trigger in the first ~250 characters of the description; make a multi-workflow skill's root a short router; heuristics, except fragile operations, which get exact scripts | R3, R5 | S10 | glm-f23, openai-f21, claude-f9 |
| Do 13 | Put what must load in the root `AGENTS.md`; treat imports, nested files and path rules as optional extras | R3 | S7 | glm-f22, open-weight-f3, claude-harness |
| Do 14 | For long runs, keep durable state in files: goal, memory, progress | R2, R7 | — | claude-g9, glm-f5, openai-f24 |

**What to stop doing.**

| # | Stop | Rides | Ids |
| --- | --- | --- | --- |
| Stop 1 | Asking the model to show its reasoning or "reflect in prose" in the reply: a refusal risk on Anthropic models that always think | R1 | claude-f3, measured-f24 |
| Stop 2 | Setting thinking depth or brevity in prose in shared text ("think step by step", "think carefully", "be brief"): effort is a harness setting. Where a configuration needs a "think carefully" line (Opus 4.8, Sonnet 5 at low effort, Qwen's template, xAI's Foundry advice), it belongs to that model's harness or adapter configuration | R1 | claude-f1, gemini-f2, open-weight-f10, openai-f18, claude-f2, qwen-f2, grok-f11 |
| Stop 3 | CRITICAL / YOU MUST, and "If in doubt, use X" | R13 | claude-f4, claude-f5 |
| Stop 4 | Repeated "ask first", or broad caution | R11 | openai-g11, openai-f3 |
| Stop 5 | Blanket "verify" or "run tests" instructions, and "read X before every edit" | R15 | claude-g11, openai-f10, openai-f11 |
| Stop 6 | Narration and formatting rules tuned to one model | R9 | claude-f19, claude-f20, openai-f17, gemini-f25 |
| Stop 7 | Vague filters in review prompts ("only high severity", "be conservative"): ask for full coverage and filter in a separate step (Anthropic guidance for Opus 4.8, Sonnet 5 and Opus 5) | — | claude-f13, measured-f14 |
| Stop 8 | Open-ended thrift ("save tokens", "don't be wasteful"): one harness team reported it made the model refuse ambitious tasks [anec]. The reason is that report, not R8's token trend: the risk lies in the text's own wording | — | openai-f23 |
| Stop 9 | The current date in shared text: OpenAI advises dropping it, Google recommends date and cutoff for Gemini 3 Flash, so the harness supplies them where a model needs them. Context countdowns are per-model harness configuration: Sonnet 4.5–5 are built for context awareness, and Opus 4.7 task budgets deliberately show one | — | openai-g10, gemini-f23, claude-f25 |
| Stop 10 | Requiring a structured status block right before a tool call: Gemini-specific, so it belongs in that model's harness or adapter notes | — | gemini-f14 |
| Stop 11 | Repeating rules the harness already states, such as Codex's user precedence and its "exceptions … do not automatically require approval" line | R5 | openai-f2, chk-codex-models |
| Stop 12 | Restating one rule in several files that load together. One model-specific exception: Anthropic's Opus 5 page pairs a conciseness instruction with a short reminder near the end of a long system prompt | R5, R13 | openai-f4, openai-f5, claude-f8, chk-claude-pages |
| Stop 13 | Revealing requirements over several turns | R10 | measured-g1, measured-f19 |

## 7. Release watch (volatile)

**Two releases since 2026-09-25, both in tracked families:** Claude Sonnet 5.5 (2026-09-28) and
GPT-6.1 Sol (2026-09-29). A re-check on 2026-10-01 of Anthropic's release notes and news, OpenAI's
API and Codex changelogs, xAI's release notes (x.ai/news refused the request), the Gemini
changelog, Z.ai's release notes, DeepSeek's updates and the labs' Hugging Face organisations found
no Haiku 5.5, Fable 5.2, Grok 4.8, Qwen 4, Gemini 3.5 Pro or Gemini 4, GPT-6 Terra, DeepSeek
V4.1-Pro or GLM-6 [chk-sonnet-55, chk-openai-gpt61, chk-releases].

**As of 2026-09-25 no generally available successor had been found**, so the newest flagships were,
and apart from those two still are, Opus 5.5 and Fable 5.1; GPT-6 Astra, Sol and Luna; Grok 4.6 and
4.7; GLM-5.3; and Qwen3.8-Max [claude-newer, openai-newer, grok-newer, glm-newer, qwen-newer,
measured-newer]. That check covered the Gemini API changelog, xAI release notes, Z.ai release notes,
the QwenCloud model changelog and Anthropic's Opus 5.5 page, OpenAI's API changelog (latest entries
then Astra 09-03, Sol and Luna 09-22) [chk-openai-changelog], Mistral's changelog and news (no LLM
after OCR 4.1, GA 08-31, which is not a general LLM) [chk-mistral-changelog, chk-mistral-news] and
Meta's Muse Spark 1.3 post [chk-meta].

**Announced, not released,** each with its status and source in its family's file: Claude Haiku 5.5
([anthropic/haiku.md](anthropic/haiku.md)); Claude Fable 5.2, rumour only
([anthropic/fable.md](anthropic/fable.md#announced-not-released)); Grok 4.8
([xai/grok.md](xai/grok.md#announced-not-released)); Qwen 4
([alibaba/qwen.md](alibaba/qwen.md#announced-not-released)); Gemini 4 and Gemini 3.5 Pro
([google/gemini.md](google/gemini.md#announced-not-released)); DeepSeek V4.1-Pro
([deepseek/deepseek.md](deepseek/deepseek.md#announced-not-released)); GLM-6.0
([zai/glm.md](zai/glm.md#announced-not-released)); Muse Spark open weights
([meta/muse-spark.md](meta/muse-spark.md#announced-not-released)); and, for features, Astra's
cross-context notes as Codex's default and Anthropic's expanded Cyber Verification Program
([openai/gpt-6-family.md](openai/gpt-6-family.md#announced-not-released-and-adjacent-releases),
[anthropic/opus.md](anthropic/opus.md#announced-not-released)). Newer variants within each family
(Mythos 5.1, GPT-5.6 Terra, Grok 4.7 Fast, the GLM-5.3 variants, the Qwen3.8 snapshots) are in the
same files.

**Families outside the tracked list.** The research recommends tracking at least Google, Moonshot
and Meta as well; their current models are in [google/gemini.md](google/gemini.md),
[moonshot/kimi.md](moonshot/kimi.md) and [meta/muse-spark.md](meta/muse-spark.md), and the other
labs' in the files listed in §4.

## 8. Forecasts

Every row is a FORECAST. Unless a row says otherwise, the horizon is 2027-03-31. At or after its
horizon each row is scored held, falsified (its "Falsified if" condition met), or unscored
(`UNVERIFIED`) where the evidence to decide it does not exist yet. Horizons, in order: 2026-11-30
(A1a, A1b, O1, X1a); 2026-12-31 (Q4, Gm2, D1); 2027-01-01 (O3); 2027-03-31 (the rest but P5 and
P8); 2027-08-22 (P5); 2028-03-14 (P8).

**Scored early, 2026-10-01.** Sonnet 5.5 shipped on 2026-09-28 [chk-sonnet-55] and GPT-6.1 Sol on
2026-09-29 [chk-openai-gpt61], which settles five rows before their horizons:
- **A1a held.** Generally available on the Claude API, Bedrock, Google Cloud, Microsoft Foundry and
  Claude Platform on AWS from 2026-09-28.
- **A2 held.** `budget_tokens`, non-default sampling and forced `tool_choice` (`any` or `tool`) all
  return 400, and adaptive thinking is on by default.
- **A3, Sonnet half: falsified.** `thinking: {"type": "disabled"}` returns 400, as forecast, but
  the falsifier is met: the docs offer `between_tools`, which turns off thinking before the first reply at
  `high` effort or below and, in a request without tools, answers without thinking "as with
  `disabled` on Claude Sonnet 5". The Haiku half stays open.
- **A4a held.** "Prompting Claude Sonnet 5.5" tells readers to remove instructions such as "hold
  all findings for the final response", wording that discourages tool use, and instructions not to
  think, though it also says Sonnet 5 prompts "should perform well without changes".
- **O3 held.** GPT-6.1 Sol, a GPT-6.x release, shipped on the API and in Codex on 2026-09-29.

**From the family research.**

| ID | FORECAST | Confidence | Basis | Falsified if |
| --- | --- | --- | --- | --- |
| A1a | Sonnet 5.5 is generally available by 2026-11-30 | Medium-high | Anthropic, 09-22: "will follow in the coming weeks" [chk-anthropic-55]; frontier releases came every 3–7 weeks in 2026 [claude-trend] | Not generally available by 2026-11-30 |
| A1b | Haiku 5.5 is generally available by 2026-11-30 | Medium | Same statement [chk-anthropic-55], repeated on 2026-09-28: it "will join the Claude 5.5 family in the coming weeks" [chk-sonnet-55]; Haiku was last refreshed Oct 2025, and 4.5 retires no sooner than 2026-10-15 [claude-newer] | Not generally available by 2026-11-30 |
| A2 | At release, Sonnet 5.5 keeps Sonnet 5's API limits (`budget_tokens` and non-default sampling return 400; adaptive thinking on by default) and adds Opus 5.5's removal of forced `tool_choice` | Medium | Five controls removed across the nine releases before Sonnet 5.5; Sonnet 5 kept continuity with 4.7-era limits; Anthropic says the 5.5 tiers bring "many of the same improvements" [claude-g10, claude-g13, claude-next] | Sonnet 5.5 accepts `tool_choice` any/tool, or a non-default temperature |
| A3 | Thinking cannot be disabled on Sonnet 5.5, nor on Haiku 5.5 | Medium-low (Sonnet); low (Haiku) | Always on for Opus 5.5 and Fable; Sonnet 5 on by default but not forced; Anthropic has not said [claude-g10, claude-g13] | Docs show a way to disable thinking |
| A4a | Sonnet 5.5 ships with its own prompting page advising removal of at least one instruction written for the previous model | High | Every Opus, Fable and Sonnet release from Opus 4.7 to Opus 5.5 did this [claude-g7 to claude-g13] | No dedicated page, or no removal advice |
| A4b | Haiku 5.5 ships with its own prompting page with removal advice | Medium-low | Haiku 4.5 had none [claude-g3] | No dedicated page, or no removal advice |
| Q1 | Qwen 4 uses the Flash-Next architecture (Gated DeltaNet with Qwen Sparse Attention, Gated Residual, N-gram Embedding, Muon) | High (rests on Alibaba's claim) | "An early preview of the architecture used in Qwen4" [qwen-g12] | The Qwen 4 release describes a different attention design |
| Q2 | Qwen 4 keeps thinking on by default, `reasoning_effort` tiers, `preserve_thinking` on by default, and compatibility with Anthropic's API and OpenAI's Responses API | Medium-high (continuity since 3.5) | [qwen-next, qwen-trend] | In-prompt thinking tags return, or `preserve_thinking` is off by default |
| Q3 | Qwen 4 keeps cross-harness training and reports headline results measured in Claude Code | Medium-high | [qwen-g9, qwen-g10, qwen-f9] | Headline results measured only in Qwen's own harness |
| Q4 | At least one Qwen 4 model is generally available by 2026-12-31 | Low-medium | "In training" at Apsara, no date; Max releases about 2.5 months apart [qwen-next, qwen-g9, qwen-g10] | No Qwen 4 release by 2026-12-31 |
| O1 | GPT-6 Astra's cross-context notes become the default in Codex by 2026-11-30 | High (announced "in the coming weeks") | [openai-next] | Not the default by 2026-11-30 |
| O2 | OpenAI keeps model-specific behaviour tuning in Codex's per-model base instructions and does not ask projects to put it in `AGENTS.md` | Medium-high | At `rust-v0.157.0`, Astra carries two lines Sol and Luna lack [chk-codex-models, openai-f12] | An OpenAI guide asks projects to add per-model autonomy lines to `AGENTS.md` |
| O3 | A GPT-6.x release or a new GPT-6 tier ships before 2027-01-01 | Medium | Releases 1.5–2.5 months apart in 2026; tiers added before (5.4 mini/nano, 5.6 Terra); against: nothing announced, Sol and Luna just launched [openai-next, openai-g9, openai-g11] | None by 2027-01-01 |
| X1a | Grok 4.8 is on the xAI API by 2026-11-30 | Low-medium | Musk's posts relayed by CellCog; CellCog's own guess from past gaps of 25–52 days is Oct–Nov; Grok 4.7 slipped at least five times [chk-grok48, grok-next] | No Grok 4.8 on the xAI API by 2026-11-30 |
| X1b | If Grok 4.8 ships, its xAI API list price is $2/$6 per 1M tokens | Medium | Grok 4.5, 4.6 and 4.7 were all $2/$6 [grok-trend] | Any other list price at launch |
| X2 | The next Grok flagship keeps reasoning mandatory, with an effort dial and encrypted reasoning returned | Medium | Mandatory since 4.5, but reversed once before [grok-trend, grok-g12, grok-f10] | The next flagship allows reasoning to be disabled |
| G1 | The next GLM flagship keeps forced thinking, with effort the only control | High | Toggle → default-on → forced [glm-trend, glm-g9] | Disabling thinking returns |
| G2 | GLM-6.0 appears on a Z.ai page with a date | Low-medium | Secondary reports; minutes say next-generation base training "has already begun" [glm-next] | No primary GLM-6.0 page by 2027-03-31 |
| G3 | The 5.3-Flash hybrid sparse and linear attention recipe reaches a larger GLM | Medium-high | "We are now scaling this recipe to larger models" [glm-next] | The next large GLM in the window uses dense or only sparse attention |
| Gm1 | The next Gemini generation rejects temperature, top_p and top_k with HTTP 400 | High (Google stated it) | [gemini-next, gemini-g8] | A next-generation model accepts them |
| Gm2 | An early Gemini 4 model is released by 2026-12-31 | Medium | Pre-training by 07-21; post-training confirmed 09-24 (9to5google, not re-fetched) [gemini-next, measured-next] | No Gemini 4 model by 2026-12-31 |
| D1 | DeepSeek V4.1-Pro is released by 2026-12-31 | Low-medium | Confirmed but undated ("This will continue until V4.1-Pro launches") [open-weight-next] | Not released by 2026-12-31 |
| M1 | Meta releases open weights for a Muse Spark model | Low | "On the roadmap" only [chk-meta] | No Muse Spark open weights by 2027-03-31 |
| C1 | Every flagship released before 2027-03-31 by the tracked labs reasons by default and exposes an effort parameter as its depth control | Medium | R1; against: xAI reversed twice, and GPT-6 Sol and Luna accept `none` | A flagship ships with reasoning off by default, or with no effort parameter |
| C2 | Release guidance keeps moving away from compensating text: Anthropic's and OpenAI's next prompting guides include removal advice, and the Grok Build system prompt at its next default-model change does not re-add enumerated risky-command lists or emphasis | Medium-high | R5; the Grok Build `prompt.md` diff Jul→Sep 2026 [grok-f5]; Anthropic's forecast of "progressively less human curation" [forward-22, anthropic-8]; against: OpenAI has re-added prompts before [openai-g5] | Either guide recommends adding emphasis, step lists or "think step by step", or the Grok Build prompt re-adds enumerated example lists or all-caps emphasis |
| C3 | In at least two of Anthropic, OpenAI, Google and xAI, a release reverses a documented behaviour direction of its predecessor (narration, autonomy, verification, verbosity or delegation) | Medium-high | R9 | Fewer than two of the four show such a reversal |
| C4 | For successors released in the window, Artificial Analysis (same index version, same effort) measures more output tokens per task than the predecessor in at least two of xAI, Google, Z.ai and Alibaba | Medium-low | R8; counter-examples Gemini 3.6, GLM-5.3 (lab), Muse Spark 1.3 (lab) | One or none of the four shows a rise |
| C5 | Claude Code and Gemini CLI both read `AGENTS.md` alongside their own file by default | Medium-low | Both conditional today [claude-harness, gemini-harness] | Either still needs a setting to read `AGENTS.md` alongside its own file |
| C6 | SWE-Bench Pro (V2) or Terminal-Bench (4.x) is retired, reset, split into a hard subset, or gets a new major version | Medium | SWE-bench Verified retired at about 80.9% [measured-g8]; Terminal-Bench 2.x saturated and reset to about 34% in 3.0 [measured-g15]; Terminal-Bench uses semantic versioning, though only 2 of the 8 tasks removed in 4.0 were cut for saturation [measured-g20] | Neither has any of these by 2027-03-31 |
| C7 | Models released after 2026-09-01 still lose compliance turn over turn in long sessions | Medium | R7 | A re-run of OctoBench, MTAC-IFBench or the factorial study on such models shows no decay; with no re-run by 2027-03-31 it stays unscored (`UNVERIFIED`) |
| C8 | On Terminal-Bench 4.x, within one evaluator's table, the best open-weight model stays more than 10 points behind the best closed model | Low-medium | DeepSeek's table: 31.2 against 51.8 [open-weight-f20]; the SWE-Bench Pro V2 gap is already 9.8 [measured-g22], and V4.1-Flash leads Opus 5 on TB 2.1 | The gap is 10 points or less on the same table and version |
| C9 | Fabrication and reward hacking stay measurably above zero | High | R6 | A system card or METR report on a model released in the window reports zero detected cheating or fabrication on its agentic evals |
| C10 | No tracked lab's official guidance asks projects to put model-specific autonomy or effort patches in `AGENTS.md`; they stay in harness base instructions or configuration | Medium-high | [openai-f12, claude-f21, claude-g12, chk-codex-models] | Any tracked lab publishes such guidance before 2027-03-31 |

**From the practice research.** The sources state these without a falsifier; the falsifiers below
are this reference's reading of them. Where the evidence record's quote does not itself carry the
forecast, the row says so.

| ID | FORECAST | Source | Horizon | Falsified if |
| --- | --- | --- | --- | --- |
| P1 | Scale washes away harnesses built for today's model weaknesses ("the ideal harness is no harness") | Noam Brown (A, one researcher) [forward-24]; LangChain says the same of its own guardrails [deterministic-22] | 2027-03-31 | A re-run on a model released in the window still shows a measurable gain from harness components added for model weaknesses (loop detection, pre-completion checklists) |
| P2 | Verification moves into post-training, so prompts stop asking for it | The practice synthesis's reading of [other-labs-6], whose quote does not carry it; R15 is the observed basis | 2027-03-31 | Anthropic's, OpenAI's or Google's next flagship guide recommends adding in-prompt verification instructions |
| P3 | The gap between skills and an always-loaded index closes | The practice synthesis's reading of Vercel [other-labs-29] (vendor), whose quote does not carry it | 2027-03-31 | A re-run of a Vercel-style comparison on models released in the window still shows the passive index ahead; with no re-run, unscored |
| P4 | Small models are trained for "harness compatibility" | Framework in [capability-tier-readers-23] (a recommendation more than a forecast); R3 shows it for larger models | 2027-03-31 | No small open model (about 30B parameters or fewer) released in the window reports training across several harnesses |
| P5 | A "human attention policy surface" governing when an agent may interrupt, keep working or decide alone appears within a year | Dan McAteer, guest essay (A) [latent-space-16] | 2027-08-22 | No major harness ships a configurable policy for interruptions and approvals beyond per-tool permissions |
| P6 | Frontier coding evaluations move toward rubrics | OpenAI Frontier Evals' stated direction [latent-space-30] | 2027-03-31 | No new major frontier coding benchmark or major version (OpenAI's, SWE-Bench's or Terminal-Bench's) scores with rubrics |
| P7 | Practitioners design loops that prompt agents instead of prompting turn by turn | A few prominent voices (A) [repo-readiness-audits-27] | 2027-03-31 | No further major harness, beyond Codex's and ZCode's `/goal`, ships a persistent goal or loop primitive |
| P8 | Context windows do not meaningfully exceed 1M tokens for about two years, so context stays scarce | Latent Space AINews, "Context Drought", 2026-03-14: "Willing to bet that context windows do not meaningfully go higher than 1M in the next 2 years" (an editor's bet, A), reached through the trend note of [latent-space-12] and read 2026-10-01 [chk-context-drought]; 1M is the common window today [open-weight-trend, chk-claude-models] | 2028-03-14 | A tracked lab's flagship released after 2026-03-14 ships with a default window above 2M tokens (Grok 4 Fast already offered 2M in 2025 [grok-g4]) |

## 9. Conflicts and gaps in the evidence

- **No cross-family `AGENTS.md` study.** No public study runs one `AGENTS.md` across current
  frontier models from several families [measured-f16].
- **Current-generation compliance is `UNVERIFIED`.** The compliance studies test only models
  released before Opus 5.5, Fable 5.1, GPT-6, Grok 4.7, GLM-5.3 and Qwen3.8. That includes
  MTAC-IFBench, published 2026-09-14 but tested on GLM-5.2 and an older model set [open-weight-f6,
  measured-f3, glm-f10].
- **Studies with lab ties.** MTAC-IFBench is co-authored by Zhipu and OctoBench by MiniMax [glm-f7,
  open-weight-f5]. Classifier Context Rot is by Anthropic Fellows [measured-g13]. Anthropic reviewed
  METR's Opus 5.5 summary, and OpenAI reviewed METR's GPT-5.6 Sol post [measured-g24, measured-g14].
- **Terminal-Bench 4.0 figures disagree between primary pages.** xAI's Grok 4.7 announcement lists
  Fable 5.1 at 57.9% and Grok 4.7 at 37.6% [chk-xai-47]. Anthropic's Opus 5.5 announcement lists
  Fable 5.1 at 55.8% and GPT-6 Astra at 57.9% [chk-anthropic-55]. xAI's own two figures for Grok 4.7
  differ: 37.6% in the announcement, 38.0% (Harbor) on the card [grok-f22]. Anthropic's Sonnet 5.5
  announcement gives 70.6% for Sonnet 5.5 against 10.3% for Sonnet 5, above the 66.4% it gave Opus
  5.5 a week earlier, and Artificial Analysis records 59.6% for Opus 5.5 [chk-sonnet-55,
  measured-g23]. This reference uses each developer's figure for its own model.
- **Artificial Analysis index versions** are not comparable: Fable 5.1 scored 66 on v4.2 and 53 on
  v4.3 [open-weight-newer].
- **Not used.** The "SWE-bench Pro 23.3% → 98%" figure compares different task sets and harnesses
  [measured-g22].
- **AA-Omniscience** measures factual-QA hallucination, not the honesty of completion claims (R6).
- **Current-generation IFBench** figures exist only as labs' self-reports; Artificial Analysis shows
  none for Opus 5.5, Sonnet 5.5, Fable 5.1 or the GPT-6 models [chk-ifbench].
- **Settled at the source.** Codex GPT-6 base instructions: earlier records called "Do not treat
  exceptions…" Astra-only [openai-f2, openai-harness]; at `rust-v0.157.0` all three tiers carry it,
  and the Astra-only lines are the "can you…" line and the "If a skill does not explicitly require
  approval…" line [chk-codex-models]. Claude Code skill descriptions: one record gives 250
  characters for listings [claude-harness]; the skills page says the model's listing truncates the
  combined `description` and `when_to_use` at 1,536 characters, and 250 is the `/skills` menu
  [chk-claude-skills].

## How to apply

- Write shared text for every family and tier that will load it: state the outcome, scope, bounds,
  stop conditions and completion bar; leave effort, thinking, narration, formatting, autonomy and
  date handling to each model's harness or adapter configuration (Do 1–14, Stop 1–13).
- Choose test models across the divergences in §5, not within one family, and include the smallest
  tier that will run the text.
- At each model or point release, re-run a small pinned set of scenarios against a dated snapshot
  (R16): aggregate scores hide item-level regressions, and aliases such as `qwen3.8-max` move.
- Do not rely on an API control or a prose rule to force a tool call or a sampling setting (R12).
- Score each forecast at its horizon; a falsified forecast reopens whatever rests on it.

## Limits and open questions

- The per-release evidence is mostly each lab's own account; independent measurement exists for
  older model pairs and a few benchmarks, several with lab ties.
- No study runs one instruction file across current flagships of several families, and none tests
  one shared file across tiers.
- Model and API facts drift monthly; the lineage tables in the model files are as of 2026-09-25,
  with Anthropic's rows, GPT-5.6 and GPT-6.1 Sol re-read on 2026-10-01.
- Re-check due: at each release in a tracked family, and at the forecast horizons above; a full
  refresh of the family sweeps is due by 2026-12-25.

## Sources

Every cited id's URL and date are in the evidence file; this section lists the sources by kind.
Read 2026-09-25 unless dated otherwise.

**Checks defined here** (verdict PASS unless stated):
- [chk-claude-caching] Anthropic prompt caching, read 2026-10-01.
  <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>
- [chk-releases] Release check of 2026-10-01: Anthropic release notes and news; OpenAI API and Codex
  changelogs; xAI release notes (x.ai/news returned 403); Gemini API changelog; Z.ai release notes;
  DeepSeek updates; Alibaba's press release of 2026-09-22 on Qwen 4; the labs' Hugging Face
  organisations.
- [chk-ifbench] Ai2 on IFBench <https://allenai.org/blog/ifbench-artificial-analysis>, the llm-stats
  board <https://llm-stats.com/benchmarks/ifbench> and Artificial Analysis's IFBench page
  <https://artificialanalysis.ai/evaluations/ifbench>, read 2026-10-01.
- [chk-context-drought] Latent Space AINews, "Context Drought", 2026-03-14 (paid; the opening
  section read 2026-10-01) <https://www.latent.space/p/ainews-context-drought>.
- [chk-nolima] Modarressi et al., NoLiMa, ICML 2025, read 2026-10-01.
  <https://arxiv.org/abs/2502.05167>
- Record details re-read at their sources on 2026-10-01: the Qwen3.7 blog, the Qwen3.8-27B and
  Qwen3-8B cards, QwenCloud's thinking guide, Simon Willison on Gemini 3.5 Flash (2026-05-19)
  <https://simonwillison.net/2026/May/19/gemini-35-flash/>, the Gemini changelog, the DeepSeek V4
  and V4.1-Flash reports, the Kimi K3 card <https://huggingface.co/moonshotai/Kimi-K3> and
  MTAC-IFBench.
- The talk in §2: Thariq Shihipar on Latent Space, "The Future of Claude Code: Mods, Mutable
  Software, & Multiplayer Agents", 2026-09-28 <https://www.youtube.com/watch?v=IZAlq-V19U8>;
  auto-generated captions read 2026-09-29.
- [chk-amp-agents] <https://ampcode.com/docs/customize/agents-md>; [chk-amp-skills]
  <https://ampcode.com/docs/customize/skills>; [chk-pi]
  <https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/docs/configuration.md>;
  [chk-copilot]
  <https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions>;
  [chk-cline] <https://docs.cline.bot/features/cline-rules>.
- [chk-claude-skills] Claude Code skills page: the combined `description` and `when_to_use` text is
  truncated at 1,536 characters in the model-facing skill listing; 250 characters is the `/skills`
  menu.
- [chk-claude-memory] Claude Code memory page: a `CLAUDE.md` of up to 4 MiB loads in full, and a
  larger one is skipped.
- [chk-claude-subagents] Claude Code subagents page: from v2.1.198, Explore inherits the main
  conversation's model instead of always running on Haiku, capped at Opus on the Claude API.
- [chk-jetbrains] JetBrains developer survey (August 2026): Codex use rose from 3% in January 2026
  to 16% in May–July 2026; Copilot fell from 29% a year earlier to 21%; Cursor from 18% in January
  to 12%.
- Terminal-Bench leaderboard: rendered without scores, `UNVERIFIED`. <https://www.tbench.ai/leaderboard>
- [review] Supplied by the independent reviewer and not re-fetched: the Gemma 4 release date,
  gpt-oss's licence, and the CNBC and Wikipedia reports on the Astra rollout.

**Checks defined in the model files**, cited here by id: [chk-claude-models] and
[chk-claude-pages] in [anthropic/claude-5-family-prompting.md](anthropic/claude-5-family-prompting.md#sources);
[chk-fable-coverage] in [anthropic/fable.md](anthropic/fable.md#sources); [chk-anthropic-55] in
[anthropic/opus.md](anthropic/opus.md#sources); [chk-sonnet-55] in
[anthropic/sonnet.md](anthropic/sonnet.md#sources); [chk-openai-reasoning] and [chk-openai-pricing]
in [openai/gpt-5.6-family.md](openai/gpt-5.6-family.md#sources); [chk-openai-gpt61],
[chk-openai-changelog] and [chk-codex-models] in [openai/gpt-6-family.md](openai/gpt-6-family.md#sources);
[chk-gptoss] in [openai/earlier-generations.md](openai/earlier-generations.md#sources);
[chk-xai-cards], [chk-xai-47] and [chk-grok48] in [xai/grok.md](xai/grok.md#sources);
[chk-glm-blogs] in [zai/glm.md](zai/glm.md#sources); [chk-gemma] in
[google/gemini.md](google/gemini.md#sources); [chk-meta] in [meta/muse-spark.md](meta/muse-spark.md#sources);
[chk-mistral-devstral2], [chk-mistral-models], [chk-mistral-news], [chk-mistral-changelog] and
[chk-vibe] in [mistral/mistral.md](mistral/mistral.md#sources).

**Labs' own pages** (release posts, model cards, prompting guides, API docs) are listed under Sources
in each family's file (§4).

**Research and independent measurement.** Context files: Lulla et al., `AGENTS.md` runtime,
2026-01-28 <https://arxiv.org/abs/2601.20404>; ETH, Evaluating `AGENTS.md`, 2026-02-12 (v2
2026-06-23) <https://arxiv.org/abs/2602.11988>. Instruction following and context: Laban et al., lost
in multi-turn, 2025-05-09 <https://arxiv.org/abs/2505.06120>; Chroma, Context Rot, 2025-07-14
<https://www.trychroma.com/research/context-rot>; McMillan, factorial study of instruction-file
structure, 2026-05-11 <https://arxiv.org/abs/2605.10039>; Arize IFScale re-run, 2026-05
<https://arize.com/blog/llm-instruction-following-benchmark-2026/>; IFBench via Artificial Analysis,
2026-05-11 <https://allenai.org/blog/ifbench-artificial-analysis>; Classifier Context Rot
(Anthropic-affiliated), 2026-05-12 <https://arxiv.org/abs/2605.12366>; constraint saturation (single
author), 2026-08-12 <https://arxiv.org/abs/2608.12426>; item-level migration regressions,
2026-08-18 <https://arxiv.org/abs/2608.17719>; MTAC-IFBench (co-authored by Zhipu), 2026-09-14
<https://arxiv.org/abs/2609.14992>; OctoBench (co-authored by MiniMax), 2026-01-15
<https://arxiv.org/html/2601.10343>. Prompting methods and tiers: Wharton Prompting Science Report
2, 2025-06-08 <https://arxiv.org/abs/2506.07142>; Better Harnesses, Smaller Models, 2026-07-09
<https://arxiv.org/html/2607.08938>; Prompting Inversion (weak), 2025-10-25
<https://arxiv.org/abs/2510.22251>; aging of prompt techniques, 2026-08-25
<https://arxiv.org/abs/2608.24641>. Time horizons and benchmarks: METR Time Horizon 1.1, 2026-01-29
<https://metr.org/blog/2026-1-29-time-horizon-1-1/>; SWE-bench Verified retired (secondary), 2026-02
<https://blog.pebblous.ai/blog/swe-bench-verified-retired/en/>; METR time horizons, 2026-05-08
<https://metr.org/time-horizons/>; METR on GPT-5.6 Sol (OpenAI reviewed), 2026-06-26
<https://metr.org/blog/2026-06-26-gpt-5-6-sol/>; Terminal-Bench 3.0, 2026-07-23
<https://www.tbench.ai/news/terminal-bench-3-0>; Terminal-Bench 4.0, 2026-08-26
<https://www.tbench.ai/news/terminal-bench-4-0>; Scale SWE-Bench Pro V2, 2026-09-22
<https://labs.scale.com/leaderboard/swe_bench_pro_public_v2>; METR on Claude Opus 5.5 (Anthropic
reviewed), 2026-09-22 <https://metr.org/blog/2026-09-22-claude-opus-5-5/>. Artificial Analysis:
Gemini 3.1 Pro, 2026-02-19 <https://artificialanalysis.ai/articles/gemini-3-1-pro-preview-new-leader-in-ai>;
Grok 4.3, 2026-04-30
<https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing>;
open-weight launches, 2026-04-30 <https://artificialanalysis.ai/articles/recent-open-weights-model-launches>;
Grok 4.5, 2026-07-08
<https://artificialanalysis.ai/articles/grok-4-5-brings-spacexai-to-the-the-intelligence-frontier>;
Gemini 3.8 Flash, 2026-09-02 <https://artificialanalysis.ai/articles/gemini-3-8-flash>; Grok 4.7,
2026-09-21 <https://artificialanalysis.ai/articles/benchmarking-grok-4-7>; GPT-6 Sol and Luna,
2026-09-22
<https://artificialanalysis.ai/articles/gpt-6-sol-and-luna-push-the-cost-efficiency-frontier>; Claude
Opus 5.5, 2026-09-22 <https://artificialanalysis.ai/articles/claude-opus-5-5>; model pages read
2026-09-25 <https://artificialanalysis.ai/models/glm-5-3>, <https://artificialanalysis.ai/models/qwen3-8-max>.
Other independent: Transluce on o3, 2025-04-16 <https://transluce.org/investigating-o3-truthfulness>;
Cursor on the Codex model harness (harness team), 2025-12-04 <https://cursor.com/blog/codex-model-harness>;
CodeRabbit on Opus 5.5 (vendor), 2026-09-22 <https://www.coderabbit.ai/blog/opus-5-5-model-review>;
DataCamp relaying OpenAI's MRCR figures on Astra (secondary), 2026-09-03
<https://www.datacamp.com/blog/gpt-6-astra>.

**Aggregators and practitioners.** Latent Space: o1 skill issue, 2025-01-12
<https://www.latent.space/p/o1-skill-issue>; Noam Brown, 2025-06-19 <https://www.latent.space/p/noam-brown>;
end of SWE-bench Verified, 2026-02-23 <https://www.latent.space/p/swe-bench-dead>; is harness
engineering real (paywalled after intro), 2026-03-05
<https://www.latent.space/p/ainews-is-harness-engineering-real>; harness engineering (Lopopolo),
2026-04-07 <https://www.latent.space/p/harness-eng>; Loopcraft (paywalled after intro), 2026-06-12
<https://www.latent.space/p/loopcraft>; evolution of the agent harness (McAteer), 2026-08-22
<https://www.latent.space/p/attention-interface>. Vercel, `AGENTS.md` outperforms skills, 2026-01-27
<https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>; LangChain, harness
engineering, 2026-02-17 <https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering>.

**Standards and security.** OWASP Top 10 for Agentic Applications, 2025-12-09
<https://genai.owasp.org/download/52117/?tmstv=1765059207>; `AGENTS.md` (repository last commit
2026-09-10) <https://agents.md/>; Aikido, hidden PUA Unicode, 2025-10-31
<https://www.aikido.dev/blog/the-return-of-the-invisible-threat-hidden-pua-unicode-hits-github-repositorties>;
Snyk, ToxicSkills on ClawHub, 2026-02-05 <https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/>;
AgentLinter (v2.3.0 2026-03-09; last commit 2026-08-14)
<https://raw.githubusercontent.com/seojoonkim/agentlinter/main/README.md>.
