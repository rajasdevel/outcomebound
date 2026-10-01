---
last_checked: 2026-10-01
volatility: VOLATILE (four models in four weeks; prices, tiers and Codex defaults still moving)
sources:
  - https://developers.openai.com/api/docs/guides/latest-model
  - https://developers.openai.com/api/docs/models/gpt-6-astra
  - https://developers.openai.com/api/docs/models/gpt-6-sol
  - https://developers.openai.com/api/docs/models/gpt-6-luna
  - https://developers.openai.com/api/docs/models/gpt-6.1-sol
  - https://developers.openai.com/api/docs/guides/reasoning
  - https://developers.openai.com/api/docs/guides/fast-mode
  - https://developers.openai.com/api/docs/changelog
  - https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra.md
  - https://deploymentsafety.openai.com/gpt-6-astra
  - https://raw.githubusercontent.com/openai/codex/rust-v0.157.0/codex-rs/models-manager/models.json
  - https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning
---

# OpenAI GPT-6: Astra, Sol, Luna and 6.1 Sol

What OpenAI's GPT-6 models are, what their API accepts, how they behave, how OpenAI says to prompt
them, what they cost, and what Codex tells them. For anyone running a GPT-6 model in Codex or
through the API, or writing an `AGENTS.md` or skill a GPT-6 model will read. GPT-5.6 is in
[gpt-5.6-family.md](gpt-5.6-family.md), earlier OpenAI models in
[earlier-generations.md](earlier-generations.md); what Codex loads is in
[harnesses/codex.md](../../harnesses/codex.md#1-instruction-files-and-precedence). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and availability (VOLATILE)

OpenAI's GPT-6 guide presents the family as three choices: **GPT-6 Astra** ("Highest
intelligence"), **GPT-6.1 Sol** ("Balanced speed, cost, and intelligence"; "Near-Astra
performance for complex work at a lower cost") and **GPT-6 Luna** ("Fastest and most
cost-effective"). GPT-6 Sol remains available; its model page points to GPT-6.1 Sol as "the newer
Sol model", and the guide asks users of `gpt-6-sol` to review the migration guidance before
switching. There is no GPT-6 Terra.

| Model | API id | Released (API) | Knowledge cutoff | `reasoning.effort` | Default |
| --- | --- | --- | --- | --- | --- |
| GPT-6 Astra | `gpt-6-astra` | 2026-09-03 | 2026-04-30 | `low`, `medium`, `high`, `xhigh`, `max` (no `none`) | not stated on the model page (Codex runs it at low) |
| GPT-6 Sol | `gpt-6-sol` | 2026-09-22 | 2026-04-20 | `none` to `max` | `medium` |
| GPT-6 Luna | `gpt-6-luna` | 2026-09-22 | 2026-05-18 | `none` to `max` | `medium` |
| GPT-6.1 Sol | `gpt-6.1-sol` | 2026-09-29 | 2026-04-30 | `low` to `max` (no `none`, no `minimal`) | `medium` |

- All four: 1,050,000-token window, at most 922,000 input tokens, 128,000 output; text and image in,
  text out; Responses and Chat Completions endpoints, Batch supported.
- **Astra's rollout.** The API changelog dates Astra 2026-09-03; CNBC and Wikipedia describe
  approved access on 09-03 and general availability on 09-04, a split the changelog does not show
  [review; chk-openai-changelog]. Phased rollout in ChatGPT and Codex [openai-g12].
- **On Microsoft Foundry** the reasoning-model matrix lists `gpt-6-astra` (2026-09-03), `gpt-6-sol`
  and `gpt-6-luna` (2026-09-22) and `gpt-6.1-sol` (2026-09-29), structured outputs supported on each,
  no access request needed (Astra needs a quota request below quota tiers 5 and 6). The Azure retail
  price list carries Astra, Sol and Luna meters effective 2026-09-01 at OpenAI's list prices for
  global standard; no GPT-6.1 Sol meter was listed on 2026-10-01. Provider details:
  [../../providers/azure-foundry.md](../../providers/azure-foundry.md#2-gpt-models-on-foundry-volatile).
- **In Codex.** Codex CLI 0.157.0 (2026-09-25) added Sol and Luna; GPT-6.1 Sol became the default
  model of Codex CLI 0.159.1 (2026-09-29) [openai-newer, chk-openai-gpt61, chk-releases].

## API surface (STABLE)

- **Tool calling.** Astra and GPT-6.1 Sol support Chat Completions but call tools only through the
  Responses API. GPT-6 Sol and Luna call functions in Chat Completions only with `reasoning_effort:
  "none"`; reasoning with tools runs on Responses.
- **Unsupported parameters.** When effort is not `none`, remove `temperature`, `top_p` and
  `top_logprobs` (and `logprobs` in Chat Completions). Astra rejects custom `temperature`/`top_p`
  and log probabilities.
- **Reasoning across turns.** GPT-6 models default to `reasoning.context: all_turns`, which needs
  `previous_response_id`, a conversation, or a replay of every output item; reasoning does not carry
  across model families [chk-openai-reasoning].
- **New with Astra** (all GPT-6, Responses API): async tool calling (`async: true`; the model keeps
  working while the application runs a tool); mid-turn steering over WebSockets; a
  `configuration_update` input item that changes reasoning effort between responses without
  rewriting the prompt prefix, in standard single-agent requests; asynchronous misalignment
  monitoring that can raise alerts or stop a conversation for review (Astra).
- **Carried over from GPT-5.6:** computer use, structured outputs, streaming, programmatic tool
  calling, multi-agent orchestration (GPT-6.1 Sol: multi-agent delegation in beta), prompt caching,
  persisted reasoning, compaction, pro mode.
- **Service tiers.** Fast mode at 2× the applicable rate for all GPT-6 models, not with EU data
  residency, and for Astra without a latency SLA. Ultrafast mode for Astra (`service_tier:
  "ultrafast"`, 2026-09-29), global processing and US data residency only. Batch and Flex at 50%.
  Regional processing adds 10%. GPT-6.1 Sol supports US and EU data residency.
- **Fixes.** On 2026-09-25 OpenAI fixed an image-encoding bug that had degraded image understanding
  in GPT-6 Sol and Luna in the API and Codex, including computer use, and advised re-running
  evaluations with image inputs.

## Behaviour (MONITOR)

From OpenAI's GPT-6 guide, which describes Astra and offers its prompts "as a starting point across
the GPT-6 model family… evaluate them with your chosen model and workload":
- **"Our most aligned model yet."** It asks more when the answer could change the outcome, and stops
  more tentatively where users expect assumptions and persistence; it also asks non-blocking
  questions while working [openai-g12, openai-f3].
- **More sensitive to instructions in skills and files such as `AGENTS.md`;** unclear or conflicting
  guidance in a skill can make it pause and block work early. OpenAI "strongly recommend[s]"
  auditing them [openai-8].
- **Lists, tables and Markdown by default,** and recurring phrases across sessions [openai-g12].
- **Delegates to subagents less often than may be wanted;** responds well to prompting on when and
  how much to delegate.
- **Tests thoroughly before calling a coding task complete,** which on small tasks can mean broader
  tests than needed; earlier models needed encouragement to test, so the same instructions now cause
  unnecessary testing [openai-f10].
- **Stronger general instruction following** and better with long instructions; coherent over long
  tasks; strong results with fewer output tokens and lower estimated API cost per task than earlier
  models despite higher per-token prices (OpenAI).
- An HN user wrote an `AGENTS.md` rule for Sol meant for moving code and, after switching to Astra,
  saw it applied "for all edits in all projects" [anec; from the detail of openai-f1].

Measurements:
- **Honesty and autonomy (system card, lab).** Astra misrepresents 4x less often than GPT-5.6 Sol on
  tasks chosen to elicit dishonesty (false reports of completed actions, tool access, verification or
  background work), and OpenAI's own surfaces add a developer prompt against it [openai-f15].
  Exposing a confirmation policy cut misaligned outcomes from 3.4% to 3.0% for Astra (18.8% to 8.0%
  for GPT-5.6 Sol) [openai-f13]. At max effort with no system controls, Astra sought workarounds after
  environment barriers in 19% of rollouts, against 64% for GPT-5.6 Sol; the card counts finding a
  safer alternative after an auto-review denial as acceptable and only retrying similar commands or
  bypassing the monitor as failure [openai-f14]. The card reports 99.99% instruction-hierarchy
  robustness [lab; measured-g21].
- **Sol and Luna (Artificial Analysis, indep).** At max effort in Codex: Sol +2 and Luna −2 on its
  Coding Agent Index against GPT-5.6, and about −100 and −75 Elo on GDPval-AA, because deliverables
  omitted required elements [openai-f19]. They hallucinated less partly by declining more
  [openai-g13].
- **Long context (lab).** Astra at 100% on an eight-needle retrieval test at 256K–512K and 96.3% at
  512K–1M [measured-f18]: needles found, not instructions followed (relayed by DataCamp).
- **SWE-Bench Pro V2 (Scale):** Astra (Codex) 90.2 [measured-g22]. Anthropic's Opus 5.5
  announcement lists Astra at 57.9% on Terminal-Bench 4.0 [chk-anthropic-55].
- No IFBench score for any GPT-6 model appears on Artificial Analysis [chk-ifbench].

## Prompting (MONITOR)

From the GPT-6 guide and OpenAI's post "Rethinking skills and prompts for GPT-6 Astra" (2026-09-11):
- **Initiative and follow-through.** OpenAI gives prompts for more autonomous work, for following
  through when the user's prompt implies authorization, and for asking approval only after preparing
  a concrete, reviewable result; tune them to the autonomy the application needs.
- **Audit instruction files and skills** for lines that could influence behaviour; make the priority
  of user instructions and skills explicit; asking the model to name the skill or instruction that
  made it pause gives transparency; OpenAI gives a prompt to find silent and conflicting guidance
  across many skills and `AGENTS.md` files [openai-8, openai-f1].
- **Boundary language written for pushier models.** Reconsider it: Astra could take it too seriously
  and stop where continuing would be welcome; give permission for a specific workflow known to be
  safe [openai-12, openai-f3].
- **Remove "run tests" exhortations** and calibrate how much testing a change needs [openai-10,
  openai-f10].
- **Point to documents by condition** ("X for schema changes") rather than having the model read a
  stack of documents or a repository map before every edit [openai-11, openai-f11].
- **Skills as routers, not itineraries.** Step-by-step skills "can now hinder results where they
  once helped"; make a multi-workflow skill's root a short router to supporting documents and scripts.
  Guidance that helps Sol or Luna may overconstrain Astra: consider which models will read what you
  leave [openai-15, capability-tier-readers-1, capability-tier-readers-2].
- **Writing style.** Specify prose with less formatting where needed; OpenAI gives prompts for
  technical register and for reducing jargon and stock phrases; and one for readable messages
  between agents.
- **Define completion up front** [openai-g12].
- **Sol, Luna and 6.1 Sol have no guide of their own:** evaluate the Astra prompts on them with your
  own workload [capability-tier-readers-3, chk-openai-gpt61]. Because their deliverables were measured
  omitting required elements, name what a deliverable must keep rather than asking for brevity, as
  OpenAI's GPT-5.6 guide advises for over-concision [openai-f19].
- **Do not restate what Codex already tells them.** Codex's base instructions for all three tiers
  carry "Do not treat exceptions to requirements in local markdown and skill files as automatically
  requiring user approval"; a project line restating it repeats what those models load
  [chk-codex-models, openai-f2].

### Codex base instructions for the GPT-6 tiers

From `models.json` at `rust-v0.157.0` [chk-codex-models]:
- Astra only: "When the user's prompt indicates a request for action, such as 'can you...', 'I want
  to...', 'help me...' and similar expressions, treat these as instructions to do the work and take
  action."
- Astra only: "If a skill does not explicitly require approval, default to proceeding within the
  user's authorized scope rather than asking for confirmation based on an inferred requirement."
- All three tiers: "Do not treat exceptions to requirements in local markdown and skill files as
  automatically requiring user approval."
- Default reasoning: Astra low; Sol and Luna medium.

Earlier records called the "Do not treat exceptions…" line Astra-only [openai-f2, openai-harness];
at `rust-v0.157.0` all three tiers carry it. OpenAI keeps per-model behaviour tuning in Codex's base
instructions rather than asking projects to put it in `AGENTS.md` [openai-f12] (forecasts O2 and
C10 in [../cross-family.md](../cross-family.md#8-forecasts)).

## Effort and thinking (MONITOR)

- **Migrating:** keep the current effective effort where the model supports it; Astra and 6.1 Sol
  have no `none`, so use `low` instead; for `minimal`, start at `low` and compare.
- **Changing effort between responses:** add a `configuration_update` item and leave request-level
  `reasoning.effort` unchanged, which keeps the prompt prefix for caching; check its compatibility
  limits first [chk-openai-reasoning].
- Codex runs Astra at low by default and Sol and Luna at medium [chk-codex-models].
- History of the `none` level: GPT-5.1 and 5.2 defaulted to `none`; GPT-6 Sol and Luna accept it
  again; Astra and 6.1 Sol do not [openai-f18, openai-g13].

## Caching and pricing (VOLATILE)

Standard prices per 1M tokens for prompts up to 272K input tokens (model pages, 2026-10-01):

| Model | Input | Cached input | Cache write | Output |
| --- | --- | --- | --- | --- |
| GPT-6 Astra | $10 | $1 (10%) | $12.50 | $50 |
| GPT-6 Sol | $2 | $0.20 (10%) | $2.50 | $10 |
| GPT-6 Luna | $0.10 | $0.01 (10%) | $0.125 | $0.50 |
| GPT-6.1 Sol | $2 | $0.10 (5%) | $2.50 | $10 |

- Prompts above 272K input tokens bill the whole request at 2× input and cache rates and 1.5×
  output. Cache writes cost 1.25× uncached input. Batch and Flex 50%; Fast mode 2×; regional
  processing +10%.
- GPT-6.1 Sol costs a fifth of Astra's rates [chk-openai-pricing].
- Caching mechanics from GPT-5.6 on (1,024-token minimum, exact cached-token boundary, `30m` TTL,
  explicit breakpoints, `prompt_cache_key` only for separate accounting): see
  [gpt-5.6-family.md](gpt-5.6-family.md#caching-mechanics-stable) and
  [practices/prompt-caching.md](../../practices/prompt-caching.md#3-openai-volatile). When migrating from GPT-5.5 or earlier, replace
  `prompt_cache_retention` with `prompt_cache_options.ttl: "30m"`.

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| GPT-6 Astra | 2026-09-03 (API, per the API changelog; phased rollout in ChatGPT and Codex) | "Most aligned". Asks more and stops more tentatively, so OpenAI supplies initiative prompts. More sensitive to `AGENTS.md` and skills: audit them. Soften boundary language written for pushier models, remove "run tests" exhortations, replace "read X before every edit", define completion up front. Defaults to lists, tables and stock phrases. No `none` effort. CNBC and Wikipedia describe approved access on 09-03 and general availability on 09-04; the API changelog does not show that split [review] | openai-g12, openai-f3, openai-f10, openai-f11, chk-openai-changelog |
| GPT-6 Sol / Luna (no GPT-6 Terra) | 2026-09-22 | Sol $2/$10 and Luna $0.10/$0.50 per 1M tokens, against Astra's $10/$50. Both support `none` and default to medium. Guidance inherited from Astra, with "evaluate with your chosen model". Artificial Analysis, at max effort in Codex: Sol +2 and Luna −2 on its Coding Agent Index against 5.6, and about −100 and −75 Elo on GDPval-AA because deliverables omitted required elements [indep] | openai-g13, openai-f19 |
| GPT-6.1 Sol | 2026-09-29 | "Near-Astra performance" for complex coding, computer use and professional work at $2/$10 per 1M tokens, cached input at 5% of input. Effort `low` to `max`, default `medium`, no `none`; tool calls only through the Responses API; reasoning carried across turns (`all_turns`); multi-agent delegation in beta. No guide of its own: OpenAI's GPT-6 prompts "address behavior observed with GPT-6 Astra; evaluate them with your chosen model". The default model of Codex CLI from 0.159.1 | chk-openai-gpt61 |

## Direction (MONITOR)

OpenAI's advice moved in four steps: stacked reminders on a literal GPT-4.1; "less is more";
fresh baselines and outcome-first prompts; leaner prompts stating each rule once [openai-trend].
With GPT-6 Astra it tells users to audit and delete instructions, although it re-added persistence
prompts in GPT-5.1 [openai-g5]. Its recommended frame is "outcome, important constraints,
available evidence, and completion bar" [openai-g11]. Autonomy swings between releases, and OpenAI
keeps its per-model tuning in Codex's base instructions rather than in project files [openai-f14,
openai-f12, chk-codex-models]. GPT-6.1 Sol followed a week after Sol and Luna; no GPT-6 Terra tier or
new Codex-specialised model was announced as of 2026-10-01, and the Codex-specialised line appears
to have ended at GPT-5.3-Codex [chk-openai-gpt61]. The release of GPT-6.1 Sol settled forecast O3
early ([../cross-family.md](../cross-family.md#8-forecasts)).

## Announced, not released, and adjacent releases

- **Astra's cross-context notes in Codex** (an experimental `config.toml` feature) "will become the
  default for Astra in the coming weeks", with less restrictive Daybreak cyber safeguards on the same
  schedule; not yet the default by Codex CLI 0.159.3 (2026-09-30) [openai-next, chk-releases]
  (forecast O1, horizon 2026-11-30).
- Codex CLI 0.158.0 was in alpha (`rust-v0.158.0-alpha.13` on 2026-09-25); OpenAI DevDay Exchange
  events from 2026-10-16 to 2026-11-11 are a plausible venue for announcements, none confirmed
  [openai-next].
- Astra gained the Ultrafast service tier on 2026-09-29, the day GPT-6.1 Sol shipped [chk-releases].
- Adjacent releases that are not general LLMs: GPT-Live-1 (09-10), GPT Image 2.5 (09-08), the Agents
  API with a managed Codex harness (beta, 09-10; computer use added 09-29), gpt-rosalind-research
  (09-08) [openai-newer, openai-next].
- No GPT-6 Terra was found in the release check of 2026-10-01 [chk-releases].

## Sources

- [chk-openai-gpt61] GPT-6.1 Sol: API changelog entry of 2026-09-29, model page
  <https://developers.openai.com/api/docs/models/gpt-6.1-sol>, GPT-6 guide and the Codex changelog
  (CLI 0.159.1), read 2026-10-01.
- [chk-openai-changelog] OpenAI API changelog: GPT-6 Astra API date 2026-09-03; no approved-access
  phase mentioned; re-read 2026-10-01. <https://developers.openai.com/api/docs/changelog>
- [chk-codex-models] Codex `models.json` at tag `rust-v0.157.0`: the GPT-6 base-instruction lines.
  <https://raw.githubusercontent.com/openai/codex/rust-v0.157.0/codex-rs/models-manager/models.json>
- [chk-openai-reasoning] and [chk-openai-pricing] are defined in
  [gpt-5.6-family.md](gpt-5.6-family.md#sources); [chk-anthropic-55] in
  [../anthropic/opus.md](../anthropic/opus.md#sources); [chk-ifbench] and [chk-releases] in
  [../cross-family.md](../cross-family.md#sources).
- Read 2026-10-01: GPT-6 guide <https://developers.openai.com/api/docs/guides/latest-model>; model
  pages for `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-6.1-sol` under
  <https://developers.openai.com/api/docs/models/>; fast-mode guide
  <https://developers.openai.com/api/docs/guides/fast-mode>; Microsoft Foundry reasoning models
  <https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning>; Azure retail prices API
  <https://prices.azure.com/api/retail/prices>.
- OpenAI, latest-model guide (GPT-6), 2026-09-03, updated 09-22; GPT-6 Astra system card, 2026-09-03
  (updated 09-09, 09-22) <https://deploymentsafety.openai.com/gpt-6-astra>; rethinking skills and
  prompts for GPT-6 Astra, 2026-09-11
  <https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra.md>; read
  2026-09-25.
- Artificial Analysis, GPT-6 Sol and Luna, 2026-09-22
  <https://artificialanalysis.ai/articles/gpt-6-sol-and-luna-push-the-cost-efficiency-frontier>;
  DataCamp relaying OpenAI's MRCR figures on Astra (secondary), 2026-09-03
  <https://www.datacamp.com/blog/gpt-6-astra>.
- [review] Supplied by an independent reviewer and not re-fetched: the CNBC and Wikipedia reports on
  the Astra rollout.
