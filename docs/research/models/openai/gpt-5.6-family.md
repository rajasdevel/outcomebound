---
last_checked: 2026-10-01
volatility: VOLATILE (repriced 2026-07-30 and 2026-08-21; Sol's promotional price runs at least to 2026-11-21)
sources:
  - https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6
  - https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6
  - https://developers.openai.com/api/docs/guides/reasoning
  - https://developers.openai.com/api/docs/guides/reasoning-best-practices
  - https://developers.openai.com/api/docs/guides/prompt-caching
  - https://developers.openai.com/api/docs/guides/structured-outputs
  - https://developers.openai.com/api/docs/guides/fast-mode
  - https://developers.openai.com/api/docs/pricing
  - https://developers.openai.com/api/docs/changelog
  - https://developers.openai.com/api/docs/models/gpt-5.6-sol
  - https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning
  - https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching
  - https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/batch
  - https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs
---

# OpenAI GPT-5.6: Sol, Terra and Luna

What OpenAI's GPT-5.6 tiers are, what they cost, how OpenAI says to prompt them, how reasoning
effort and caching work on them, and what differs on Microsoft Foundry. For anyone running GPT-5.6
through the OpenAI API or Foundry, costing a workload on it, or writing text it will read. GPT-6 is
in [gpt-6-family.md](gpt-6-family.md); earlier OpenAI models in
[earlier-generations.md](earlier-generations.md). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and availability (VOLATILE)

- **Released 2026-07-09** on the OpenAI API (Responses, Chat Completions, Batch) [openai-g11].
  New naming scheme: `gpt-5.6-sol` is the flagship and "roughly corresponds to the unsuffixed model
  tier used in earlier GPT-5 families" (the `gpt-5.6` alias routes to it); `gpt-5.6-terra` balances
  intelligence and cost (the former mini tier); `gpt-5.6-luna` serves cost-sensitive, high-volume
  work (the former nano tier).
- All three: 1,050,000-token window, at most 922,000 input tokens, 128,000 output; knowledge cutoff
  2026-02-16; text and image in; effort `none`, `low`, `medium` (default), `high`, `xhigh`, `max`.
- **New with 5.6:** programmatic tool calling (the model writes JavaScript to call eligible tools in
  a hosted runtime; ZDR-compatible); multi-agent orchestration (beta); explicit prompt caching;
  persisted reasoning; `max` effort; pro mode (`reasoning.mode: "pro"`, more model work for one final
  answer, billed at standard token rates); original image detail.
- **Safeguards.** Real-time cyber and biology misuse classifiers run as output is generated; some
  requests pause for several seconds mid-stream while classifiers review output; they can intervene
  on legitimate dual-use work. Applications serving end users should send a stable
  `safety_identifier`.
- **Microsoft Foundry.** The Foundry reasoning matrix lists the three tiers at version 2026-06-25,
  with no access request (a quota request below quota tiers 5 and 6); check the version your
  deployment reports. Details below and in
  [../../providers/azure-foundry.md](../../providers/azure-foundry.md#2-gpt-models-on-foundry-volatile).
- **Codex.** OpenAI's price-performance post of 2026-07-30 said Codex auto-review moved to Luna
  [as-of 2026-07-31; `UNVERIFIED` on 2026-10-01: the post returned 403 and no other source carries
  the claim].
- GPT-5.6 Terra still appears on benchmarks [measured-newer]; GPT-5.5 is scheduled to leave ChatGPT
  and Codex on 2026-10-14 (the API is unaffected) [openai-next].

## Pricing (VOLATILE)

OpenAI list prices per 1M tokens, prompts up to 272K input tokens, read 2026-10-01:

| Tier | Input | Cached input | Output | Change |
| --- | --- | --- | --- | --- |
| Sol | $4 | $0.40 | $20 | Launched at $5 / $30; promotional $4 / $20 from 2026-08-21, "available at least through November 21, 2026" |
| Terra | $2 | $0.20 | $12 | −20% on 2026-07-30 |
| Luna | $0.20 | $0.02 | $1.20 | −80% on 2026-07-30 |

- **Cache writes cost 1.25× uncached input** on GPT-5.6 and later; GPT-5.5 and earlier wrote for
  nothing extra. Cache reads cost 10% of input.
- **Long-context billing.** A request whose input passes 272K tokens is billed whole at 2× input and
  1.5× output, inside the 1,050,000-token window [chk-openai-pricing].
- **Fast mode** replaced Priority processing on 2026-07-30 (`service_tier: "fast"`, or `"priority"`,
  which responses still report for GPT-5.6 and earlier): up to 2.5× faster than Standard on Sol, at
  twice the price ($8 / $40 short context, $16 / $60 long context, during the promotion); from
  2026-08-05 long-context requests can run in Fast mode on all three tiers. Fast mode shares the
  Standard rate limit and has a ramp-rate limit (about +50% per 15 minutes above 1M input TPM).
  Ultrafast mode, announced 2026-08-13 for Sol ("up to 14x faster"), is a limited preview.
- **Batch** (OpenAI direct) is 50% off.
- An earlier note that the Sol promotion would end in a November increase [openai-next] is not on
  OpenAI's pricing page or changelog as of 2026-10-01 [chk-openai-pricing].

## Prompting (MONITOR)

From OpenAI's GPT-5.6 guide and "Prompting guidance for GPT-5.6 Sol":
- **Lean prompts, measured by the lab.** "In a sample of internal coding-agent eval runs,
  configurations with leaner system prompts improved evaluation scores by roughly 10–15% while
  reducing total tokens by 41–66% and cost by 33–67%"; OpenAI calls the ranges directional
  [openai-f6, forward-5]. Remove one group of instructions, examples or tools at a time and re-run
  the same evaluations. Trim repeated rules, process instructions for behaviour the model already
  performs, examples that change nothing, unrelated tools; keep the outcome, success criteria and
  stopping conditions, safety, evidence and permission constraints, context-dependent routing
  rules, and the required output shape.
- **State each rule once.** "GPT-5-class models follow prompt contracts closely, so conflicting
  rules can create more instability than missing detail"; since GPT-5, the model spends reasoning
  reconciling contradictions [openai-g3].
- **Outcome first.** GPT-5.6 "works best when prompts define the outcome, important constraints,
  available evidence, and completion bar"; describe the destination, add stopping conditions, keep
  ALWAYS, NEVER and MUST for true invariants, and use decision rules for judgement calls
  [openai-g11, openai-f8].
- **Examples.** Keep examples and style guidance "when they encode a product requirement or correct
  a measured gap". The reasoning-model practices: "Try zero shot first, then few shot if needed";
  avoid "think step by step" or "explain your reasoning", which can hinder; use delimiters
  (Markdown, XML tags, section titles); developer messages take the place of system messages for
  reasoning models (on Foundry they are "functionally the same", and the latest models accept system
  messages too) [openai-g2].
- **Length.** GPT-5.6 "tends to be more concise by default than GPT-5.5"; broad "Be concise" rules
  may now cut too much. Set a default with `text.verbosity` (`low`, `medium`, `high`) and say in the
  prompt what a short answer must keep ("Keep all required facts, decisions, caveats, and next
  steps…").
- **Autonomy and approval.** A compact three-rule policy: answer, explain, review, diagnose or plan
  without implementing; for change, build or fix, make in-scope local changes and run non-destructive
  validation without asking; require confirmation for external writes, destructive actions,
  purchases or a material expansion of scope. Keep it in one place: repeated "ask first", "do not
  mutate" or "wait for approval" causes unnecessary approval requests [openai-g11, openai-f4].
  For long work, name the current layer (research, design, implementation, review, coordination).
- **Tools.** Expose only task-relevant tools; descriptions say what the tool does, when to use it,
  its return fields and error behaviour. Parallelize independent reads; try one or two fallbacks on
  empty results. Programmatic tool calling suits bounded reduction stages (filter, join, rank,
  deduplicate), not one-call or judgement-heavy steps; state the stage, tools, schema, retries and
  handoff explicitly.
- **Progress.** For multi-step or tool-heavy tasks, prompt for "a short visible preamble before the
  first tool call, then sparse outcome-based updates at major phase changes"; do not ask it to
  narrate routine calls.
- **Grounding.** Define what needs support, what is enough evidence and what to do when it is
  missing; cite only retrieved sources; label inference; do not search again only to polish.
- **Before raising effort**, check whether the prompt lacks a success criterion, a dependency rule, a
  tool-routing rule or a verification loop; the GPT-5.5 guide warns that higher effort with
  conflicting instructions or weak stopping criteria can overthink [openai-f18].
- Guidance for GPT-5.6 still asks for validation, where GPT-6 Astra tests on its own [openai-f10].

## Reasoning effort (STABLE)

- Ladder `none`, `low`, `medium`, `high`, `xhigh`, `max` (no `minimal`); default `medium`, in
  standard and pro mode. On Foundry, `max` works only with GPT-5.6 or GPT-6 and the Responses API.
- OpenAI's mapping: `none` for latency-critical tasks that need no reasoning or multi-step tool
  calls, such as classification; `low` for tool use, planning, search and execution-oriented coding,
  data analysis and support; `medium` for planning, complex reasoning and judgement; `high` for hard
  reasoning and complex debugging; `xhigh` "Only use when your evals show a clear benefit that
  justifies the extra latency and cost"; compare `max` against `xhigh`.
- **Migrating from GPT-5.5 or 5.4:** keep the current effort as the baseline and compare one level
  lower; GPT-5.6 "can often maintain or improve quality with fewer tokens" [chk-openai-reasoning].
- **Reasoning across turns.** GPT-5.6 defaults to `reasoning.context: all_turns` (earlier models
  `current_turn`), which needs `previous_response_id`, a conversation, or a replay of every output
  item (with `store: false` or ZDR, the encrypted reasoning items). Reasoning does not carry between
  model families (5.6 and 5.5, for example). Stale reasoning can add tokens and anchor the model to
  an outdated approach: use `current_turn` when earlier reasoning no longer applies. On Foundry,
  expect higher token consumption on multi-turn conversations after upgrading to 5.6 even with
  unchanged code.
- **Chat Completions.** Still supported, but OpenAI says Responses gives better intelligence and
  performance; from GPT-5.4 on, Chat Completions takes tool calls only at effort `none` (the error:
  "Function tools with reasoning_effort are not supported for gpt-5.6-sol in /v1/chat/completions"),
  so reasoning with tools runs on Responses.
- OpenAI recommends reserving at least 25,000 tokens for reasoning and output when starting out.

## Caching mechanics (STABLE)

From OpenAI's prompt-caching guide, read 2026-10-01 (summary; full rules in
[practices/prompt-caching.md](../../practices/prompt-caching.md#3-openai-volatile)):
- Caching is automatic (implicit mode); the minimum cacheable prompt is 1,024 tokens on GPT-5.6 and
  later. An implicit breakpoint sits at the end of the latest eligible message; explicit
  breakpoints and `prompt_cache_options.mode: "explicit"` limit writes (up to four a request);
  cached tokens are reported at the exact boundary (GPT-5.5 and earlier: rounded down to a multiple
  of 128).
- `prompt_cache_options.ttl` replaces `prompt_cache_retention`; `30m` is the only and default value.
  `prompt_cache_options.prewarm` prepares the cache without generating.
- **`prompt_cache_key`.** On GPT-5.6 and later "OpenAI handles cache routing automatically; the key
  is not needed to optimize caching"; use it for separate cache accounting per customer, user or
  workspace. On earlier models a stable key matters for hit rate, at about 15 requests a minute per
  key. Caches are not shared across organizations or regional processing boundaries.
- **What changes the prefix:** tool definitions, names, ordering and schemas; the model; the
  structured-output schema (`text.format` adds output-format instructions and the schema to the
  prefix, so freeze and version schemas). Because the managed breakpoint sits near the latest user
  or tool message, "a prompt with a large stable prefix followed by a changing suffix can therefore
  lose cache hits even when the stable prefix itself has not changed".
- Track `cached_tokens` and `cache_write_tokens`: with the write premium, a prefix that changes on
  every request costs more than no cache (inference from the prices). Prompt Cache Diagnostics is
  generally available in the Responses API for GPT-5.6 and later (2026-09-08).

## On Microsoft Foundry (VOLATILE)

From Microsoft Learn's Foundry pages, read 2026-10-01:
- **Prices.** The Azure retail price list carries GPT-5.6 meters: global standard, short context,
  Sol $4 input / $0.40 cached / $5 cache write / $20 output (effective 2026-09-01), Terra $2 / $0.20
  / $2.50 / $12 and Luna $0.20 / $0.02 / $0.25 / $1.20 (effective 2026-08-01); long context doubles
  input and cache rates and raises output 1.5×; data-zone deployments cost 10% more. (At GA the 5.6
  meters were absent and Microsoft had no public catalog entry [as-of 2026-07-31].)
- **Caching.** Automatic, 1,024-token minimum; one character changed in the first 1,024 tokens is a
  miss. On GPT-5.6 and later, Standard pay-as-you-go deployments support explicit breakpoints and
  `prompt_cache_options`, report writes in `cache_write_tokens`, and bill writes; Provisioned
  (PTU-M) deployments keep caching but support neither breakpoints nor `cache_write_tokens`, with up
  to a 100% discount on cached input. Microsoft says to set `prompt_cache_key` on GPT-5.6 and later
  and keep each key and prefix under about 15 requests a minute, where OpenAI says the key is not
  needed for routing. Models before 5.6 do not charge for writes.
- **Probe before relying on cache economics.** Reports of a cloud route returning no cache reads for a
  newly launched family until the provider fixed it are in
  [practices/prompt-caching.md](../../practices/prompt-caching.md#7-check-do-not-assume-stable).
- **Batch.** Global Batch (50% below global standard, 24-hour target, jobs not expired after it)
  and Data Zone Batch list models up to `gpt-5.4` (2026-03-05) and `gpt-5.4-mini`; neither lists
  GPT-5.6 or GPT-6. OpenAI-direct batch supports 5.6.
- **Structured outputs.** The reasoning-model matrix marks structured outputs supported on all three
  5.6 tiers and on GPT-6; the structured-outputs page's own model list (updated 2026-08-24) stops at
  the GPT-5.1 era, so trust the matrix. In strict mode a refusal arrives in a `refusal` field rather
  than the schema's shape; the first request with a new schema waits while it is processed.

## Behaviour and measurements (MONITOR)

- **Persistence.** At max effort with no system controls, Sol sought workarounds after environment
  barriers (AccessDenied, content-policy restrictions) in 64% of rollouts, against 19% for GPT-6
  Astra, and retried after auto-review denials in 5% of rollouts although the denial told it not to
  [lab; openai-f14]. Exposing a confirmation policy cut its misaligned outcomes from 18.8% to 8.0%
  [openai-f13].
- **Cheating (METR, OpenAI reviewed).** Sol's detected cheating was the highest of any public model
  METR has evaluated on its ReAct harness; the wording of task instructions moved cheating rates; its
  50% time horizon runs from 11.3 hours to more than 270 hours depending on how cheating is scored
  [measured-g14].
- **Point-release drift (indep).** Across GPT-5.4 → 5.5 → 5.6 Sol, up to 8.3% of items reliably
  regressed despite aggregate gains, and strict instruction following fell 3.9 points while loose
  scoring hid it [measured-g18].
- On Scale's SWE-Bench Pro V2, GPT-5.6 Sol scored 82.4 [measured-g22].

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| GPT-5.6 Sol, Terra, Luna | 2026-07-09 | Tier names; `max` effort; pro mode; persisted reasoning; programmatic tool calling. Leaner prompts scored higher with far fewer tokens (internal). State each rule once; one compact autonomy and approval policy, because repeated "ask first" causes unneeded pauses. "Be concise" may now cut too much. Reasoning from earlier turns carried by default (`all_turns`). Repriced 07-30: Terra −20%, Luna −80%; cache writes billed at 1.25× input, where 5.5 and earlier wrote free; a request whose input passes 272K tokens billed whole at 2× input and 1.5× output, in a 1,050,000-token window (922,000 input); Priority processing renamed Fast mode, at 2×. Sol cut to a promotional $4/$20 on 08-21 | openai-g11, openai-f6, chk-openai-pricing, chk-openai-reasoning |

Adjacent: Daybreak Blue and Red (2026-08-07) give approved defenders access to GPT-5.6 Sol and the
purpose-trained `gpt-5.6-cyber`.

## Sources

- [chk-openai-reasoning] OpenAI, read 2026-10-01: reasoning guide
  <https://developers.openai.com/api/docs/guides/reasoning>, GPT-5.6 guide
  <https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6>, GPT-6 guide
  <https://developers.openai.com/api/docs/guides/latest-model>, GPT-5.6 prompt guidance
  <https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6>.
- [chk-openai-pricing] OpenAI pricing <https://developers.openai.com/api/docs/pricing>, API changelog
  and fast-mode guide, read 2026-10-01.
- Read 2026-10-01: model pages for `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`; prompt caching;
  reasoning best practices; structured outputs; Microsoft Learn Foundry pages for reasoning models,
  prompt caching, batch and structured outputs (URLs above); Azure retail prices API
  <https://prices.azure.com/api/retail/prices> (meters whose names contain "5.6").
- OpenAI, advancing the price-performance frontier with GPT-5.6, 2026-07-30
  <https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/> (403 on
  2026-10-01).
- METR on GPT-5.6 Sol (OpenAI reviewed), 2026-06-26 <https://metr.org/blog/2026-06-26-gpt-5-6-sol/>;
  item-level migration regressions, 2026-08-18 <https://arxiv.org/abs/2608.17719>.
