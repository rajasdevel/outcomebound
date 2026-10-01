---
last_checked: 2026-10-01
volatility: VOLATILE (minimums, lifetimes, prices and invalidation rules change with each model release) / STABLE (the prefix mechanism and the design rules that follow from it)
sources:
  - https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - https://platform.claude.com/docs/en/build-with-claude/effort
  - https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages
  - https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback
  - https://developers.openai.com/api/docs/guides/prompt-caching
  - https://developers.openai.com/api/docs/guides/upgrading-to-gpt-5p6-sol
  - https://developers.openai.com/api/docs/pricing
  - https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching
  - https://docs.x.ai/developers/advanced-api-usage/prompt-caching/multi-turn.md
  - https://ai.google.dev/gemini-api/docs/caching
---

# Prompt caching

Re-check when a provider changes its caching rules, minimums, lifetimes or prices, or a model
generation ships; in any case by 2027-01-01.

How prompt caching works at Anthropic, OpenAI, Azure OpenAI, xAI and Google, what it costs, what
silently defeats it in an agent loop, and how to see whether it happened. For anyone who writes
always-loaded text or long prompts, designs an agent loop or a harness, or estimates what a workload
will pay for tokens. How much of a long context a model can use, and compaction, are in
[long-context-and-compaction.md](long-context-and-compaction.md); what each cloud route changes is
in [`../providers/`](../providers/).

**Evidence classes**, as in [the index](../README.md): M measured; L lab or vendor documentation or
guidance; S standard or protocol specification; P practitioner consensus; A anecdote or one
uncontrolled report; F forecast; O own result. **Citations.** Bracketed ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl); `[chk-…]` ids are pages read on
2026-10-01, listed under Sources. Almost everything here is a provider's documentation about its own
product (L).

## Key findings

**CM2. Prompt caching rewards a stable prefix and fails silently.** Providers cache the longest
unchanged prefix of a request; at Anthropic a change invalidates its level and every later one, in
the order tools, system, messages. A prefix below the model's minimum (512 to 4,096 tokens at
Anthropic, 1,024 at OpenAI from GPT-5.6, 4,096 on Gemini 3.x) is processed uncached with no error.
Text that changes between requests belongs after the stable text, and only the usage fields show
whether caching happened. L.

**CM3. Agent loops defeat caches in ways a single request does not.** An Anthropic breakpoint looks
back only 20 blocks; parallel requests that share a prefix each miss it until the first response
begins; a top-level change of effort or tools restarts the cache, while per-message effort,
`configuration_update` items and mid-conversation system messages keep it; edited history breaks it.
From GPT-5.6, OpenAI bills cache writes at 1.25× input, so a prefix that never repeats costs more
than no cache. L.

## 1. How it works, and what follows for text (STABLE)

- **The mechanism.** A provider caches the longest unchanged prefix of a request and bills later
  reads of it at a fraction of the input price. At Anthropic the prefix runs tools, then system,
  then messages, and "Changes at each level invalidate that level and all subsequent levels"
  [chk-claude-caching]. OpenAI and xAI match from the start of the request in the same way, and
  Google advises putting large common content at the beginning [chk-openai-caching,
  chk-xai-caching, chk-gemini-caching]. Azure OpenAI: "Place stable or repeated content at the
  beginning of the prompt and dynamic content at the end. Keep conversation context append-only"
  [chk-azure-caching]. L.
- **Stable text first.** It follows that text which changes between requests (a date, a run id, a
  digest, a generated list in unstable order, per-user lines, conditional sections, a tool set that
  varies) belongs after the stable text, never inside an always-loaded file above it: one such line
  re-bills everything after it on every request. Order a request from the most stable part to the
  least: frozen instructions and tool definitions, then per-session, per-turn and per-request
  content. Inference from the documented mechanism; the list of such lines comes from an earlier
  practitioner note (A [as-of 2026-07-31], not re-checked). It is a cost reason, beside the
  prompting reason of Stop 9 in
  [models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text), for keeping dates out of
  shared text.
- **Settings inside the prefix.** Tool definitions and a structured-output schema are part of what
  is cached at OpenAI and Azure OpenAI ("Structured output schema is appended as a prefix to the
  system message") [chk-openai-caching, chk-azure-caching]; a schema or tool set that changes per
  request therefore changes the prefix. Keep each schema fixed for as long as a cached prefix should
  hold (inference). L.
- **What caching does not do.** It does not shorten the context ("Cached prompt prefixes still
  occupy the context window" [chk-claude-context]), and it does nothing for context rot
  [latent-space-12 detail]. L.

## 2. Anthropic (VOLATILE)

All from Anthropic's prompt-caching, effort, mid-conversation system message and refusal pages, read
2026-10-01 [chk-claude-caching, chk-claude-mid-system, chk-claude-refusals]. L.

- **Breakpoints.** Up to 4 `cache_control` breakpoints; a write happens only at a breakpoint.
- **Minimum prefix.** 512 tokens on Fable 5.1, Mythos 5.1, Opus 5.5, Opus 5, Sonnet 5.5, Fable 5
  and Mythos 5; 1,024 on Opus 4.8, Sonnet 5, Sonnet 4.6, Sonnet 4.5, Opus 4.1, Opus 4 and Sonnet 4;
  2,048 on Mythos Preview, Opus 4.7 and Haiku 3.5; 4,096 on Opus 4.6, Opus 4.5 and Haiku 4.5. The
  minimum does not fall steadily by generation. A shorter prompt "will be processed without
  caching, and no error is returned". These minimums hold on the Claude API, Claude Platform on AWS,
  Google Cloud and Microsoft Foundry; Bedrock documents its own minimums, failure behaviour and usage
  field names.
- **What invalidates.** A change to tool definitions invalidates everything; toggling web search or
  citations, or switching fast mode, invalidates system and messages; `tool_choice` and images
  invalidate messages only; thinking parameters and a top-level effort change always invalidate
  messages, and system and tools too on models that render the setting ahead of them. Setting effort
  explicitly to the model's default changes nothing. A dropped thinking block changes the prefix
  from its position on. Caches are per model.
- **What keeps it.** A per-message effort change (beta) on Fable 5.1, Mythos 5.1, Opus 5.5, Opus 5 and
  Sonnet 5.5 (Fable 5 returns 400 for it); a mid-conversation system message, instead of an edit to
  `system`, on Fable 5.1, Mythos 5.1, Fable 5, Mythos 5, Opus 5.5, Opus 4.8, Opus 5 and Sonnet 5.5
  (not Sonnet 5), on the Claude API, Bedrock and Google Cloud (not Microsoft Foundry); tool additions
  under the `inline-tools-2026-09-15` beta; and thinking blocks passed back unchanged. Claude Code
  keeps its cache across effort changes on Opus 5.5 and Fable 5.1 from v2.1.280, per Latent Space
  ([harnesses.md](../harnesses/cross-harness.md#3-loading-harness-by-harness)).
- **Prices.** A 5-minute write costs 1.25× base input, a 1-hour write 2×, a read 0.1× (0.025× on
  Fable 5.1 and Mythos 5.1, 0.05× on Opus 5.5). Against sending the prefix uncached each time, a
  5-minute entry comes out ahead once one later request reads it, and a 1-hour entry once two do
  (computed from the multipliers). Anthropic estimates that Fable 5.1's read price, 75% below Fable
  5's, lowers the price of typical workloads by about 25% and of highly agentic ones by up to about
  45% [chk-fable-page].
- **Lifetime.** "The cache is refreshed for no additional cost each time the cached content is
  used." The lifetime counts from the start of the request that wrote or read the entry: "if a
  response takes 4 minutes to stream, a follow-up request that reuses the same cached prefix must
  start within about 1 minute of that response completing" (5-minute entry).
- **Lookback.** "The lookback window is 20 blocks": a breakpoint finds an earlier entry only within
  20 positions, counting itself; on the Claude API a run of consecutive `tool_use` blocks counts as
  one position, as does a run of `tool_result` blocks. If a growing conversation pushes the
  breakpoint 20 or more blocks past the last write, the lookback misses with no error, so an agent
  loop places a new breakpoint before 20 blocks pile up (inference).
- **Fan-out.** "A cache entry only becomes available after the first response begins": parallel
  requests sent before then miss it, so send one, wait for its response to begin, then fan out.
  Anthropic's Fable 5 guide adds that long-lived subagents which keep their context save time and
  money through cache reads [chk-claude-pages].
- **Pre-warming.** A request with `max_tokens: 0` writes the cache and returns no output; it is
  rejected with `stream: true`, extended thinking, structured outputs, a forced `tool_choice`, or
  inside a batch. Anthropic presents it as removing "the cache-miss latency penalty on the first user
  interaction" for latency-sensitive applications, to be repeated at least every 5 minutes to keep a
  5-minute entry warm, with the 1-hour duration for longer gaps. A pre-warm with other thinking or
  effort settings than the real requests writes an entry they never hit. Traffic that already
  repeats the prefix within the lifetime keeps it warm without one (inference).
- **Isolation and limits.** Caches are separate per organization, and per workspace on the Claude
  API, Claude Platform on AWS and Microsoft Foundry (per organization on Bedrock and Google Cloud).
  Cache hits do not count against rate limits.
- **Another model starts cold.** A manual retry on a fallback model "writes the fallback model's
  prompt cache from scratch"; Anthropic's fallback credit covers that miss when its own fallback runs
  [chk-claude-refusals].

## 3. OpenAI (VOLATILE)

From OpenAI's prompt-caching guide, GPT-5.6 upgrade guide, reasoning guide and pricing page, read
2026-10-01 [chk-openai-caching, chk-openai-reasoning, chk-openai-pricing]. L.

- **Minimum and breakpoints.** Caching is on by default. From GPT-5.6 the minimum is 1,024 visible
  input tokens, an implicit breakpoint sits at the end of the latest eligible message, and cached
  tokens are reported at the exact boundary; GPT-5.5 places implicit breakpoints every 2,048 tokens,
  and it and earlier models report cached tokens rounded down to a multiple of 128. An explicit mode
  (`prompt_cache_options.mode: explicit`, with `prompt_cache_breakpoint` on a content block) allows
  up to four writes a request; content after the last breakpoint is billed uncached with no write.
- **Routing.** On GPT-5.6 and later "the key is not needed to optimize caching on these models", and
  separate keys can keep separate cache accounting; on earlier models a stable `prompt_cache_key`
  helps routing, with traffic kept to about 15 requests a minute per key and heavier traffic sharded
  across keys.
- **Lifetime.** From GPT-5.6, `prompt_cache_options.ttl` of `30m`, the only and default value;
  earlier models use `prompt_cache_retention`: `in_memory` (typically 5–10 minutes inactive, up to an
  hour) or `24h` (extended retention, up to 24 hours).
- **Price.** From GPT-5.6, cache writes cost 1.25× uncached input, where GPT-5.5 and earlier wrote for
  nothing extra; reads cost 0.1× (0.05× on GPT-6.1 Sol). Input above 272K tokens bills the whole
  request at long-context rates, which on GPT-6 models double the cache rates too. With a write
  premium, a prefix that changes on every request costs more than no cache (inference from the
  prices): prefix stability is a cost requirement, not only an optimization.
- **Changing suffixes.** GPT-5.6's managed breakpoint sits near the latest user or tool message, so
  "a prompt with a large stable prefix followed by a changing suffix can therefore lose cache hits
  even when the stable prefix itself has not changed" (upgrade guide).
- **Settings inside the prefix.** The full rendered context is cached, tool definitions included;
  `text.format` adds the schema, so a changed schema no longer matches. On GPT-6 models a
  `configuration_update` item changes effort between responses without touching the prefix.
- **Usage.** `usage.input_tokens_details.cached_tokens` and `cache_write_tokens` in the Responses API.

## 4. Azure OpenAI in Microsoft Foundry (VOLATILE)

Microsoft's prompt-caching page for Azure OpenAI (updated 2026-08-12), read 2026-10-01
[chk-azure-caching]. L. Azure follows OpenAI's request shapes with its own deployment types; the
rest of the Foundry route is in [`../providers/azure-foundry.md`](../providers/azure-foundry.md).

- **Minimum and match.** A request must be at least 1,024 tokens and its first 1,024 tokens
  identical; "A single character difference in the first 1,024 tokens results in a cache miss". On
  GPT-5.5 and earlier, hits after the first 1,024 tokens come in 128-token increments; GPT-5.6 and
  later report the exact boundary.
- **Breakpoints and keys on GPT-5.6 and later.** Standard pay-as-you-go deployments support explicit
  breakpoints (`implicit` mode, the default, adds one on the latest message and so leaves three
  explicit write slots; `explicit` mode uses only the caller's, and with none disables caching and
  write charges); up to four writes a request, and reads consider up to the latest 50 breakpoints.
  Provisioned (PTU-M) deployments cache but support no breakpoints. Microsoft advises setting
  `prompt_cache_key` and reusing it for requests that share a long prefix, about 15 requests a minute
  per prefix and key before some miss. Models before GPT-5.6 return 400 for `prompt_cache_options` or
  `prompt_cache_breakpoint`.
- **Lifetime.** On GPT-5.6 and later `prompt_cache_options.ttl` `30m` is a minimum lifetime ("the
  service might retain it longer"); earlier models choose `in_memory` (cleared within 5 to 10 minutes
  of inactivity, always within an hour of last use) or `24h` extended retention (default on
  `gpt-5.5`). Caches are not shared between Azure subscriptions.
- **Price.** Reads are discounted for Standard deployments and up to 100% for Provisioned ones; from
  GPT-5.6, writes can be charged on top. Pricing is the same for both retention policies.
- **Usage.** `prompt_tokens_details.cached_tokens`; from GPT-5.6, Standard pay-as-you-go deployments
  also report `cache_write_tokens`, and PTU-M deployments do not.

## 5. xAI and Google (VOLATILE)

- **xAI.** Matching leading messages are cached automatically; "Any change to earlier messages breaks
  the cache. Only append new messages at the end." A reasoning model must get back its
  `reasoning_content` (or continue with `previous_response_id`), omitting it being "the top cause of
  cache misses"; the `x-grok-conv-id` header raises the hit rate [grok-f17, chk-xai-caching]. L.
- **Google.** Implicit caching is on by default from Gemini 2.5, with a minimum of 4,096 tokens on the
  3.x models (3.1 Pro Preview and 3.5 to 3.8 Flash) and 2,048 on 2.5; cached input is priced at 10%
  of input on the models checked; requests that share a prefix should be sent close together; the
  Interactions API supports implicit caching only [chk-gemini-caching]. L.

## 6. What breaks a cache in an agent loop (STABLE)

A summary of §2–§5 for checking a harness or a prompt design:

- volatile text in always-loaded files, or anywhere above stable text;
- changed tool definitions, or a tool set that varies between requests;
- edited earlier history instead of appended turns (append-only history is also what preserved
  thinking needs: R4 in [models.md](../models/cross-family.md#3-trends-r1r16));
- a top-level change of effort or thinking settings, where per-message effort or a
  `configuration_update` item would keep the cache;
- a switch of model: each model writes its own entries, so a retry or a router lands on a cold cache.
  A Claude Code engineer gives breaking the prompt cache as one reason the harness does not route
  between models by default, and notes that a forked agent reuses the parent's cache
  ([harnesses.md](../harnesses/cross-harness.md#131-one-practitioners-account-t1t7); A);
- requests fanned out before the first response begins;
- a conversation that grows past the lookback window between writes.

## 7. Check, do not assume (STABLE)

- The usage fields show reads and writes: Anthropic's `cache_read_input_tokens` and
  `cache_creation_input_tokens`, OpenAI's `cached_tokens` and `cache_write_tokens`, Azure's
  `cached_tokens` (and `cache_write_tokens` where §4 says), Gemini's `total_cached_tokens`. Zero reads
  across repeated identical prefixes means something in the prefix changes, or the prefix is below
  the minimum (both counts zero, at Anthropic) [chk-claude-caching, chk-openai-caching,
  chk-azure-caching, chk-gemini-caching]. L.
- One team saw a cloud provider's route for a newly launched model family report no cache reads at
  all until the provider fixed it (A [as-of 2026-07], not re-checked). Probe the route actually used,
  gateway included ([`../providers/litellm.md`](../providers/litellm.md)), before estimating what a
  workload will pay.

## How to apply

1. Order every request stable text first: no dates, run ids, digests or unordered generated lists in
   always-loaded files, and per-request content after the stable prefix (§1).
2. Before estimating what a workload pays, read the cache fields in the usage report on the route
   actually used (§7).
3. In agent loops: keep history append-only; change effort through per-message effort or
   `configuration_update`, and instructions through mid-conversation system messages where the route
   supports them; place breakpoints within the lookback window; fan out only after the first response
   begins (§2–§6).
4. On a model that bills cache writes (Anthropic always; OpenAI and Azure from GPT-5.6), cache only a
   prefix that will be read again within its lifetime (§2, §3).

## Limits and open questions

- Caching facts are provider documentation that changes monthly; cloud routes (Bedrock, Google
  Cloud, Microsoft Foundry) and gateways can differ from the provider's own API
  ([`../providers/`](../providers/)).
- Two findings rest on earlier readings not re-checked: the list of lines that typically break a
  cache (2026-07-31) and the cloud route that reported no cache reads (2026-07).
- No independent measurement of hit rates in agent loops was found; the rules above are inference
  from the documented mechanism.

## Sources

Read 2026-10-01 unless dated otherwise. Ids in brackets resolve in the evidence files.

- [chk-claude-caching] Anthropic, prompt caching
  <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>, and effort
  <https://platform.claude.com/docs/en/build-with-claude/effort>.
- [chk-claude-mid-system] Anthropic, mid-conversation system messages
  <https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages>.
- [chk-claude-refusals] Anthropic, refusals and fallback
  <https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback>.
- [chk-claude-context] Anthropic, context windows
  <https://platform.claude.com/docs/en/build-with-claude/context-windows>.
- [chk-claude-pages] Anthropic, prompting Claude Fable 5
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5>,
  and the Fable 5 announcement, 2026-06-09 <https://www.anthropic.com/news/claude-fable-5-mythos-5>.
- [chk-fable-page] Anthropic, Claude Fable (now the Fable 5.1 page) <https://www.anthropic.com/claude/fable>.
- [chk-openai-caching] OpenAI, prompt caching
  <https://developers.openai.com/api/docs/guides/prompt-caching> and upgrading to GPT-5.6 Sol
  <https://developers.openai.com/api/docs/guides/upgrading-to-gpt-5p6-sol>.
- [chk-openai-reasoning] OpenAI, reasoning <https://developers.openai.com/api/docs/guides/reasoning>
  and using GPT-6 <https://developers.openai.com/api/docs/guides/latest-model>.
- [chk-openai-pricing] OpenAI, pricing <https://developers.openai.com/api/docs/pricing> and the model
  pages for GPT-5.6 and GPT-6.
- [chk-azure-caching] Microsoft, prompt caching with Azure OpenAI in Microsoft Foundry Models,
  updated 2026-08-12 <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching>.
- [chk-xai-caching] xAI, prompt caching and multi-turn caching
  <https://docs.x.ai/developers/advanced-api-usage/prompt-caching/multi-turn.md>.
- [chk-gemini-caching] Google, Gemini API caching, last updated 2026-09-02
  <https://ai.google.dev/gemini-api/docs/caching>, and pricing <https://ai.google.dev/gemini-api/docs/pricing>.
- Evidence records: [grok-f17], [latent-space-12].
