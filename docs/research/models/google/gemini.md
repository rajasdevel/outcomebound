---
last_checked: 2026-09-25
volatility: VOLATILE (Flash ships about every three weeks; Gemini 4 in post-training)
sources:
  - https://ai.google.dev/gemini-api/docs/latest-model
  - https://ai.google.dev/gemini-api/docs/gemini-3
  - https://ai.google.dev/gemini-api/docs/changelog
  - https://ai.google.dev/gemini-api/docs/prompting-strategies
  - https://ai.google.dev/gemini-api/docs/function-calling
  - https://ai.google.dev/gemma/docs/core
---

# Google Gemini (and Gemma)

How Google's Gemini models changed in how they should be prompted, from Gemini 2.5 (March 2025) to
Gemini 3.8 Flash (September 2026), what Google's API now enforces, and what is announced. For anyone
running Gemini in Gemini CLI, Antigravity or through the API, or testing shared text on it. Google
sits outside the tracked list of [../cross-family.md](../cross-family.md#scope) and is one of its
comparison groups. Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations). The family sweep was read
2026-09-25; facts re-read later carry their own date.

## Identity and availability (VOLATILE)

- **Current frontier text model: Gemini 3.8 Flash** (2026-09-02), the default for the Antigravity
  managed agent. **Gemini 3.1 Pro Preview** (2026-02-19) is still the newest Pro, still in preview
  [gemini-newer, gemini-g10, gemini-g6].
- Also: gemini-3.8-live (09-15), gemini-3.8-flash-tts (09-22), antigravity-preview-09-2026 (09-17)
  [gemini-newer]. The re-check of 2026-10-01 found no Gemini 3.5 Pro or Gemini 4 [chk-releases].
- Antigravity CLI replaced Gemini CLI for consumers with Gemini 3.5 Flash (2026-05-19)
  [gemini-g7]; what Gemini CLI and Antigravity load is in [harnesses/gemini-cli.md](../../harnesses/gemini-cli.md#1-instruction-files-and-precedence) and
  [harnesses/others.md](../../harnesses/others.md#antigravity-googles-consumer-harness).

## API surface (STABLE)

- **Thinking.** Built in since Gemini 2.5 Pro (2025-03), so no chain-of-thought prompting; depth
  went from an integer `thinking_budget` (2.5 Flash, 0–24576) to `thinking_level` (Gemini 3);
  `thinking_budget` "no longer recommended" from 3.5 Flash; `minimal` added with 3 Flash and removed
  with 3.7 Flash (levels low, medium, high) [gemini-g1, gemini-g2, gemini-g4, gemini-g5, gemini-g7,
  gemini-g9, gemini-f5].
- **Defaults:** medium from 3.5 Flash (it had been high); 3.1 Pro high; 3.5 Flash-Lite `minimal`
  [gemini-g7, gemini-f5, gemini-f24].
- **Sampling and prefill.** From Gemini 3, keep temperature at 1.0 (lower can loop). From 3.6 Flash,
  sampling parameters are deprecated and ignored, with HTTP 400 promised for future generations,
  and prefilled model turns return 400 for "all future Gemini model releases" [gemini-g4, gemini-g8,
  gemini-f3, gemini-f16].
- **Reasoning across turns.** Thought signatures, preserved from 3.5; reasoning carries across turns
  automatically [gemini-g4, gemini-g7].
- **Custom tools.** Gemini 3.1 Pro has a `-customtools` endpoint for when the model skips custom
  tools for bash [gemini-g6].
- **Caching.** Implicit caching on by default from Gemini 2.5, minimum 4,096 tokens on the 3.x
  models (3.1 Pro Preview and 3.5 to 3.8 Flash) and 2,048 on 2.5; cached input priced at 10% of
  input on the models checked ([practices/prompt-caching.md](../../practices/prompt-caching.md#5-xai-and-google-volatile)).

## Behaviour (MONITOR)

- **Verbosity swung:** up in 3.5 Flash (one practitioner measured 14,403 output tokens for a single
  SVG prompt on 2026-05-19, A), down in 3.6 (17% fewer output tokens than 3.5, Artificial Analysis
  cited by Google), up in 3.8 (about 30% more output tokens and 40% more cost per task than 3.7,
  indep) [gemini-f25, gemini-f7].
- **3.6 Flash** takes fewer steps and makes fewer unwanted edits on diagnostic tasks [gemini-g8,
  gemini-f18].
- **3.7 Flash** "Clarifies intent when needed" and follows instructions "with greater fidelity"
  [gemini-g9].
- **3.8 Flash** is designed to "work harder": smaller reasoning steps, iterative tool calls,
  self-checking, more tokens by design, with effort the documented cost control [gemini-g10].
- **Hallucination (AA-Omniscience, indep):** 88% on Gemini 3 Pro to 50% on 3.1 Pro [gemini-f20].
- **Capability:** Google's own card puts 3.8 Flash at 19.1% on Terminal-Bench 4.0 against 51.8% for
  Opus 5 [gemini-trend]; on Scale's SWE-Bench Pro V2 it scored 58.8 [measured-g22]; IFBench put
  Gemini 3 Flash at 78.0% [measured-g11]. Google shows no evidence for the trend to longer
  unattended runs (R2).
- **As a monitor,** Gemini 3.1 missed dangerous actions more often after long benign context
  [measured-g13].

## Prompting (MONITOR)

- Google's guidance is short and direct with no chain-of-thought scaffolding; it trains behaviour in
  at each release [gemini-f1, gemini-f7].
- Google lists "when the model is permitted to make assumptions versus when it must pause execution
  to ask" among the agent behaviours a prompt can steer [gemini-f12].
- **Flash-specific clauses (3 Flash):** state the current date and the January 2025 knowledge cutoff
  [gemini-g5, gemini-f23]. OpenAI advises the opposite for its models, so the harness supplies the
  date where a model needs it ([../cross-family.md](../cross-family.md#6-what-the-trends-imply-for-shared-text),
  Stop 9).
- **Flash-Lite subagents:** for 3.5 Flash-Lite (default `minimal`), set `thinking_level` to medium or
  high for autonomous subagents "to prevent premature tool termination" [gemini-f24].
- **Status block before a tool call** is Gemini-specific; it belongs in that model's harness or
  adapter notes (Stop 10) [gemini-f14].
- **Gemini CLI** gives instruction files "absolute precedence" over its default workflows but not
  over its safety mandates, which matters for its "reproduce the bug with a test" default
  [gemini-f19].

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Gemini 2.5 Pro Exp | 2025-03-25 | Thinking built in, so no chain-of-thought prompting; every later model ships with it | gemini-g1 |
| Gemini 2.5 Flash | 2025-04-17 | Integer `thinking_budget` (0–24576): reasoning depth becomes an API setting | gemini-g2 |
| Gemini 2.5 GA | 2025-06-17 | Adaptive thinking on Pro; temperature still tunable | gemini-g3 |
| Gemini 3 Pro Preview | 2025-11-18 | `thinking_level` replaces the budget. Keep temperature at 1.0 (lower can loop), drop chain-of-thought scaffolding, write concise direct prompts. Antigravity launched. Shut down 2026-03-09 | gemini-g4 |
| Gemini 3 Flash Preview | 2025-12-17 | Adds `minimal`; Flash-specific clauses: state the current date and the January 2025 cutoff | gemini-g5, gemini-f23 |
| Gemini 3.1 Pro Preview | 2026-02-19 | Still the current Pro, still in preview. A `-customtools` endpoint for when the model skips custom tools for bash. Artificial Analysis: hallucination 88% → 50% against 3 Pro [indep] | gemini-g6, gemini-f20 |
| Gemini 3.5 Flash | 2026-05-19 | Default effort high → medium; reasoning carries across turns automatically; sampling parameters and `thinking_budget` "no longer recommended". Antigravity CLI replaces Gemini CLI for consumers | gemini-g7 |
| Gemini 3.6 Flash + 3.5 Flash-Lite | 2026-07-21 | Sampling parameters deprecated and ignored, 400 promised in future generations; prefilled model turns return 400 for "all future Gemini model releases". Fewer steps and fewer unwanted edits on diagnostic tasks; 17% fewer output tokens than 3.5 Flash (Artificial Analysis, cited by Google). For 3.5 Flash-Lite (default `minimal`), set `thinking_level` to medium or high for autonomous subagents "to prevent premature tool termination" | gemini-g8, gemini-f7, gemini-f24 |
| Gemini 3.7 Flash | 2026-08-13 | `minimal` removed (low/medium/high, default medium). "Clarifies intent when needed"; follows instructions "with greater fidelity" | gemini-g9 |
| Gemini 3.8 Flash | 2026-09-02 | Designed to "work harder": smaller reasoning steps, iterative tool calls, self-checking, more tokens by design; effort is the documented cost control. Default for the Antigravity managed agent. Artificial Analysis: about 30% more output tokens and 40% more cost per task than 3.7 [indep]. Google's card: 19.1% on Terminal-Bench 4.0 against 51.8% for Opus 5 | gemini-g10, gemini-f7, gemini-trend |

*Direction.* Google moved control out of prompt wording into API settings it enforces, and removed
the old controls: temperature, thinking budget, prefill and `minimal` [gemini-trend]. Its guidance
is short and direct with no chain-of-thought scaffolding; it trains behaviour in at each release,
and token use has moved both ways [gemini-f1, gemini-f7, gemini-f25]. Flash ships about every three
weeks; Pro has sat at a 3.1 preview since February [gemini-trend].

## Pricing (VOLATILE)

Google has scheduled standard pricing for Gemini 3.6–3.8 Flash, double the introductory rate, from
2027-01-01 [gemini-next].

## Announced, not released

| Model | Announced | Status | Source |
| --- | --- | --- | --- |
| Gemini 4 | pre-training by 2026-07-21; post-training 2026-09-24 | Release "as soon as possible", hoped "much earlier" than the end of 2026. Leaked "Gemini 4 Pro" checkpoints (TestingCatalog, 09-23) unconfirmed | gemini-next; 9to5google quoting Kavukcuoglu, not re-fetched [measured-next] |
| Gemini 3.5 Pro | 2026-05-19 (I/O) | Status unclear per Google; with partners since 07-21; missed its June target | gemini-next |

Forecasts Gm1 (the next generation rejects sampling parameters with 400) and Gm2 (an early Gemini 4
model by 2026-12-31) are scored in [../cross-family.md](../cross-family.md#8-forecasts).

## Gemma (open weights)

Gemma 4 (E2B, E4B, 12B, 26B A4B, 31B; 2026-04-02 [review]) is Apache-2.0, with built-in function
calling, pitched for "highly capable autonomous agents" [chk-gemma]. The research did not cover how
to prompt it, and it adds no trend evidence.

## Sources

- [chk-gemma] Gemma docs (Gemma 4); release date not shown on the page read.
  <https://ai.google.dev/gemma/docs/core>
- [review] The Gemma 4 release date, supplied by an independent reviewer and not re-fetched.
- [chk-releases] is defined in [../cross-family.md](../cross-family.md#sources).
- Google, read 2026-09-25: Gemini thinking updates, 2025-03-25
  <https://blog.google/technology/google-deepmind/gemini-model-thinking-updates-march-2025/>; Gemini
  2.5 Flash, 2025-04-17 <https://developers.googleblog.com/en/start-building-with-gemini-25-flash/>;
  Gemini 3 guide, 2025-11-18 (updated 2026-09-23) <https://ai.google.dev/gemini-api/docs/gemini-3>;
  what's new in Gemini 3.5, 2026-05-19 <https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5>;
  latest-model page, 2026-07-21 (snapshot 2026-07-30) and 2026-09-02
  <https://web.archive.org/web/20260802003901/https://ai.google.dev/gemini-api/docs/latest-model>,
  <https://ai.google.dev/gemini-api/docs/latest-model>; Gemini 3.7 Flash, 2026-08-13
  <https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-3-7-flash/>;
  Gemini CLI system prompt, 2026-09-08
  <https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/prompts/snippets.ts>;
  living: changelog <https://ai.google.dev/gemini-api/docs/changelog> (re-read 2026-10-01),
  prompting strategies (updated 2026-09-17) <https://ai.google.dev/gemini-api/docs/prompting-strategies>,
  function calling <https://ai.google.dev/gemini-api/docs/function-calling>.
- Secondary: 9to5google quoting Koray Kavukcuoglu on Gemini 4 post-training, 2026-09-24 (URL not
  recorded) [measured-next]; Zvi Mowshowitz on Gemini 3 Pro, 2025-11-24
  <https://thezvi.substack.com/p/gemini-3-pro-is-a-vast-intelligence>; Simon Willison on Gemini 3.5
  Flash, 2026-05-19, re-read 2026-10-01 <https://simonwillison.net/2026/May/19/gemini-35-flash/>.
- Artificial Analysis: Gemini 3.1 Pro, 2026-02-19
  <https://artificialanalysis.ai/articles/gemini-3-1-pro-preview-new-leader-in-ai>; Gemini 3.8 Flash,
  2026-09-02 <https://artificialanalysis.ai/articles/gemini-3-8-flash>.
