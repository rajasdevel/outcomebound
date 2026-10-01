---
last_checked: 2026-09-25
volatility: VOLATILE (reasoning toggled three times; Grok 4.8 announced without a date)
sources:
  - https://x.ai/news/grok-4-7
  - https://media.x.ai/v1/website/4p7card-5eccc980.pdf
  - https://media.x.ai/v1/website/card-4p6-4cd2dc57.pdf
  - https://docs.x.ai/developers/model-capabilities/text/reasoning.md
  - https://docs.x.ai/developers/advanced-api-usage/prompt-caching/multi-turn.md
  - https://docs.x.ai/developers/community/microsoft-foundry.md
---

# xAI Grok (xAI now operating as SpaceXAI)

How xAI's Grok models changed in how they should be prompted, from Grok 3 (February 2025) to Grok
4.7 (September 2026), what their API requires, and what is announced. For anyone running Grok in
Grok Build, Cursor or through the API, or testing shared text on it. Grok is a tracked family in
[../cross-family.md](../cross-family.md#scope); what Grok Build loads is in
[harnesses/others.md](../../harnesses/others.md#grok-build-xai). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations). The family sweep was read
2026-09-25; the Grok 4.6 and 4.7 cards were re-read 2026-10-01 [chk-xai-cards].

## Identity and availability (VOLATILE)

- **Current:** Grok 4.7 (2026-09-21) and Grok 4.6 (2026-08-12). Grok 4.7 Fast (09-21) is served only
  in Cursor and Grok Build; grok-build-0.1 remains on the API; grok-4.20-multi-agent is in beta
  [grok-newer].
- **Grok 4.7:** a larger base model (2.1T parameters, per Decrypt); longer RL weighted to multi-hour
  tasks; trained on the Grok Bot harness; supplemental training on anonymized Cursor workflow data;
  list price $2 / $6 per 1M tokens, as for 4.5 and 4.6 [grok-g12, grok-trend].
- Grok 4.5 to 4.7 are co-trained with Cursor data and the Grok Bot harness and evaluated mainly in
  Grok Build [grok-f14].

## API surface (STABLE)

- **Reasoning is mandatory from Grok 4.5** (low, medium, high; default high), with `xhigh` from 4.6.
  The history is not monotonic: Grok 4 always reasoned and returned an error if `reasoning_effort`
  was set; Grok 4 Fast and 4.1 Fast brought back non-reasoning slugs; Grok 4.3 offered `none`
  [grok-g2, grok-g4, grok-g6, grok-g8, grok-g10].
- **Returned reasoning.** Grok 4.7 always returns `reasoning.encrypted_content` on the Responses API;
  passing reasoning items back unchanged keeps its reasoning, and cache hits, across turns, though a
  client that ignores the field "keep[s] working" [grok-g12, grok-f17].
- **Rejected on reasoning models:** penalty parameters and `stop` [grok-f10].
- **Caching.** Matching leading messages are cached automatically; "Any change to earlier messages
  breaks the cache. Only append new messages at the end." A reasoning model must get back its
  `reasoning_content` (or continue with `previous_response_id`), omitting it being "the top cause of
  cache misses"; the `x-grok-conv-id` header raises the hit rate
  ([practices/prompt-caching.md](../../practices/prompt-caching.md#5-xai-and-google-volatile)) [grok-f17].
- **Context:** 2M on Grok 4 Fast (2025), 1M on Grok 4.3, cut to 500K on Grok 4.5 [grok-g4, grok-g8,
  grok-g10].
- **Server-side tools** (Agent Tools API, with Grok 4.1 Fast), often called in parallel [grok-g6].
- **Injected safety prefix.** In 2025 the API injected published safety-policy prefixes ahead of the
  caller's system prompt for grok-4-0709, grok-4-fast and grok-code-fast-1; whether a prefix is
  injected for 4.5 to 4.7 is `UNVERIFIED` (the prompts repository's last commit is 2025-11-17)
  [grok-harness]. The Grok 4 card calls the system prompt the "primary safeguard" [grok-g2].

## Behaviour and measurements (MONITOR)

- **Literal system-prompt following.** Grok 4.20 follows the system prompt more closely, which by
  xAI's own audit also makes it easier to steer with a misuse system prompt (0.32, against 0.16 for
  Grok 4); AgentDojo attack success 0.33 [lab; grok-g7, grok-f8]. IFBench: about 83% for Grok 4.20
  (Beta), 81% for Grok 4.3 [indep; measured-g11, grok-g8].
- **Hallucination (AA-Omniscience, indep)** moved 22%, 25%, 54%, 34%, 29% across releases: Grok 4.5
  rose from 25% to 54% while accuracy rose [grok-f19, grok-g10]. Re-check behaviour at each release.
- **Tokens per task (indep).** Grok 4.7 at xhigh used about 81k output tokens per Artificial
  Analysis Intelligence Index task, against 38k for Grok 4.6 at xhigh and 36k at high; xAI had
  pitched Grok 4.5 on token efficiency [grok-f12].
- **Long context.** Artificial Analysis measured Grok 4.7 3.7 points below 4.6 on its long-context
  reasoning test, though xAI claims better long-context handling; xAI's docs recommend context
  compaction for long agent loops [grok-f18].
- **Self-verification (xAI's claims).** Grok 4.6 and 4.7 self-test more on long runs [grok-g11,
  grok-f13]. The Grok 4.7 card puts it at 46.3% on CursorBench 4.0 at xhigh (43.9% at high), a
  benchmark Cursor publishes; the card names no outside party for that run. The Grok 4.6 card
  describes an earlier checkpoint set to speed up its own inference, "required to verify end-to-end
  gains before opening a pull request": in five hours it tried 297 candidate optimizations, discarded
  those without a measured end-to-end gain (several had passed microbenchmarks) and opened seven pull
  requests [lab; grok-f13 detail, chk-xai-cards].
- **Terminal-Bench 4.0:** 37.6% in the Grok 4.7 announcement, 38.0% (Harbor) on its card; the same
  announcement lists Fable 5.1 at 57.9% [grok-f22, chk-xai-47].
- **Misuse cooperation.** xAI's later audit found Grok 4.1 cooperating more with misuse (0.33) and
  validating user delusions more (0.08) than Grok 4 [grok-g5].

## Prompting (MONITOR)

- **No live text-model guide.** xAI's only text-model prompting guide, for grok-code-fast-1 (specific
  context, explicit goals, agentic tasks over one-shot questions; for API builders a detailed system
  prompt, XML or Markdown sections, native tool calling, append-only history for cache hits), now
  returns 404; the model retired 2026-05-15 [grok-g3, grok-f15]. xAI's docs say short, specific
  instructions are followed more reliably [grok-f15].
- **The live guidance is the Grok Build system prompt,** which between July and September 2026
  replaced lists of risky example commands with five compact principles, among them reversibility and
  blast radius [grok-f5].
- Grok Build tells the model to "report anything blocked or unverified" and treats quoted messages
  and copied UI metadata as context, not instructions; chat instructions override instruction files
  [grok-f6, grok-f7, grok-f2].
- **Think-mode prompting** is still recommended on xAI's Microsoft Foundry page, which belongs in a
  per-model adapter rather than shared text [grok-f11].
- Pass `encrypted_content` back for cache and quality, and keep history append-only.

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Grok 3 / 3 mini (Think) | 2025-02-19 consumer; API reported 2025-04-09 | RL-trained reasoning; `grok-3-mini` accepted `reasoning_effort` low/high and returned its trace. Chat-era; no agent guidance | grok-g1 |
| Grok 4 / Heavy | 2025-07-09 | Reasoning always on; setting `reasoning_effort` returned an error. RL for native tool use. The API injected a published safety prefix; the card calls the system prompt the "primary safeguard" | grok-g2 |
| grok-code-fast-1 | 2025-08-28 | xAI's only text-model prompting guide: specific context, explicit goals, agentic tasks over one-shot questions; for API builders a detailed system prompt, XML or Markdown sections, native tool calling, append-only history for cache hits. Guide now 404; model retired 2026-05-15 | grok-g3, grok-f15 |
| Grok 4 Fast | 2025-09-19 | One set of weights for reasoning and non-reasoning modes, chosen by slug; 2M context; "40% fewer thinking tokens" | grok-g4 |
| Grok 4.1 | 2025-11-17 | RL aimed at style and personality. xAI's later audit: more misuse cooperation (0.33) and more validation of user delusions (0.08) than Grok 4 | grok-g5 |
| Grok 4.1 Fast + Agent Tools API | 2025-11-19 | Separate reasoning and non-reasoning slugs; long multi-turn training; server-side tools, often in parallel | grok-g6, grok-f10 |
| Grok 4.20 | API 2026-03-10; card 2026-04-07 | Follows the system prompt more closely, which by xAI's own audit also makes it easier to steer with a misuse system prompt (0.32, against 0.16 for Grok 4). AgentDojo attack success 0.33. Artificial Analysis: record-low 22% hallucination, about 83% IFBench, measured on the Beta [indep] | grok-g7, grok-f8 |
| Grok 4.3 | ~2026-04-30 | One slug with effort none/low/medium/high (xhigh now listed); 1M context. Artificial Analysis: 81% IFBench, 98% τ²-Bench Telecom [indep] | grok-g8 |
| Grok Build CLI + grok-build-0.1 | CLI beta 2026-05-14 (SuperGrok 05-25); model API beta 2026-05-29; open source 2026-07-14 | xAI's own coding harness. Reads `AGENTS.md` plus Claude Code's instruction files, skills, hooks and MCP servers; plan mode and subagents | grok-g9 |
| Grok 4.5 | 2026-07-08 | Developed with Cursor, with supplemental training on anonymized Cursor workflow data. Reasoning cannot be disabled (low/medium/high, default high); context cut to 500k; default model in Grok Build. Artificial Analysis: hallucination rose from 25% to 54% while accuracy rose [indep] | grok-g10 |
| Grok 4.6 | 2026-08-12 | Aimed at long-running agents; adds `xhigh`. More self-testing on long runs (xAI); most card benchmarks ran in Grok Build | grok-g11 |
| Grok 4.7 (+ 4.7 Fast, Cursor and Grok Build only) | 2026-09-21 | Larger base model (2.1T parameters, per Decrypt). Longer RL weighted to multi-hour tasks; claimed better self-verification; trained on the Grok Bot harness. Always returns `reasoning.encrypted_content`; passing it back recommended, ignoring it still works. Effort low/medium/high (default)/xhigh. Terminal-Bench 4.0: 37.6% in the announcement, 38.0% (Harbor) on the card. Artificial Analysis: about 81k output tokens per task at xhigh against 38k for 4.6; −3.7 points on long-context reasoning [indep]. List price $2/$6 | grok-g12, grok-f12, grok-f18, chk-xai-47, grok-f22 |

*Direction.* From chat assistant to long-horizon coding agent co-trained with Cursor data
[grok-trend, grok-g10, grok-g12]. Reasoning went mandatory (Grok 4), optional again (4 Fast, 4.1
Fast, 4.3 `none`), and mandatory from 4.5 [grok-g2, grok-g4, grok-g8, grok-g10]. xAI removed its
only text-model guide; the live guidance is the open-source Grok Build system prompt, which between
July and September 2026 replaced lists of risky example commands with five compact principles
[grok-f5, grok-f15]. Independently measured hallucination went 22%, 25%, 54%, 34%, 29%, so behaviour
has to be re-checked at each release [grok-f19].

## Announced, not released

| Model | Announced | Status | Source |
| --- | --- | --- | --- |
| Grok 4.8 | Musk's X posts, 2026-09-13 and 09-14 | 2.5T parameters on a new C++ stack; "will finish training this week and start RL"; "a noticeable improvement" over 4.7. No date; not in the xAI docs; not found in the release check of 2026-10-01 (x.ai/news refused the request) | relayed by CellCog [chk-grok48], chk-releases |

Forecasts X1a (Grok 4.8 on the API by 2026-11-30), X1b ($2 / $6 if it ships) and X2 (reasoning stays
mandatory) are scored in [../cross-family.md](../cross-family.md#8-forecasts). CellCog's own guess
from past gaps of 25–52 days is October–November; Grok 4.7 slipped at least five times
[grok-next].

## Sources

- [chk-xai-cards] Grok 4.7 card <https://media.x.ai/v1/website/4p7card-5eccc980.pdf> and Grok 4.6
  card <https://media.x.ai/v1/website/card-4p6-4cd2dc57.pdf>, read 2026-10-01.
- [chk-xai-47] xAI, Grok 4.7 announcement (Terminal-Bench 4.0 figures), 2026-09-21.
  <https://x.ai/news/grok-4-7>
- [chk-grok48] CellCog, Grok 4.8 release date (relays Musk's X posts of 2026-09-13 and 09-14).
  <https://www.cellcog.ai/blog/grok-4-8-release-date>
- [chk-releases] is defined in [../cross-family.md](../cross-family.md#sources).
- xAI, read 2026-09-25: Grok 3, 2025-02-19 <https://x.ai/news/grok-3>; Grok 4, 2025-07-09
  <https://x.ai/news/grok-4> and model card, 2025-08-20
  <https://data.x.ai/2025-08-20-grok-4-model-card.pdf>; grok-code-fast-1, 2025-08-28
  <https://x.ai/news/grok-code-fast-1> and its prompting guide (archived 2025-11-18)
  <http://web.archive.org/web/20251118014240/https://docs.x.ai/docs/guides/grok-code-prompt-engineering>;
  Grok 4 Fast, 2025-09-19 <https://x.ai/news/grok-4-fast>; Grok 4.1, 2025-11-17
  <https://x.ai/news/grok-4-1>; Grok 4.1 Fast, 2025-11-19 <https://x.ai/news/grok-4-1-fast>; Grok 4.20
  model card, 2026-04-07 <https://data.x.ai/2026-04-07-grok-4-20-model-card.pdf>; May 15 retirement
  guide, 2026-05 <https://docs.x.ai/developers/migration/may-15-retirement.md>; grok-build-0.1,
  2026-05-29 <https://x.ai/news/grok-build-0-1>; Grok 4.5 model card, 2026-07-14 (revised 07-20)
  <https://media.x.ai/v1/website/4p5-5184fdf9.pdf>; Grok 4.6, 2026-08-12 <https://x.ai/news/grok-4-6>;
  Grok Build system prompt and loader (see [harnesses/others.md](../../harnesses/others.md#grok-build-xai)); undated: reasoning
  <https://docs.x.ai/developers/model-capabilities/text/reasoning.md>, multi-turn caching
  <https://docs.x.ai/developers/advanced-api-usage/prompt-caching/multi-turn.md>, Microsoft Foundry
  <https://docs.x.ai/developers/community/microsoft-foundry.md>.
- Secondary: Decrypt on the Grok 4.7 launch, 2026-09-21
  <https://tech.yahoo.com/ai/gemini/articles/xai-launches-grok-4-7-171603280.html>.
- Artificial Analysis: Grok 4.3, 2026-04-30
  <https://artificialanalysis.ai/articles/xai-launches-grok-4-3-with-improved-agentic-performance-and-lower-pricing>;
  Grok 4.5, 2026-07-08
  <https://artificialanalysis.ai/articles/grok-4-5-brings-spacexai-to-the-the-intelligence-frontier>;
  Grok 4.7, 2026-09-21 <https://artificialanalysis.ai/articles/benchmarking-grok-4-7>.
