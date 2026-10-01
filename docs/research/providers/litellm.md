---
last_checked: 2026-10-01
volatility: MONITOR (verdicts are per release; the proxy ships several releases a week)
sources:
  - https://docs.litellm.ai/docs/providers/azure/azure_anthropic
  - https://docs.litellm.ai/docs/completion/drop_params
  - https://docs.litellm.ai/docs/completion/provider_specific_params
  - https://docs.litellm.ai/docs/proxy/forward_client_headers
  - https://docs.litellm.ai/docs/completion/prompt_caching
  - https://docs.litellm.ai/docs/batches
  - https://github.com/BerriAI/litellm/releases
  - https://github.com/BerriAI/litellm/issues/25957
  - https://github.com/BerriAI/litellm/issues/22963
  - https://github.com/BerriAI/litellm/issues/18219
  - https://github.com/BerriAI/litellm/pull/32254
  - https://github.com/BerriAI/litellm/pull/33573
---

# LiteLLM and other gateways: what passes through

Re-check before upgrading a gateway or relying on a new parameter passing through it.

What the LiteLLM proxy forwards, drops or rewrites between a client (a harness or an application) and
a model provider, with Claude on Microsoft Foundry and OpenAI-shaped routes as the main cases, and
what its recent releases changed. For anyone who puts a gateway in front of a model and needs a
feature, header or usage field to arrive intact. The provider side of each route is in
[azure-foundry.md](azure-foundry.md) and [claude-cloud-platforms.md](claude-cloud-platforms.md).

**Evidence classes**, as in [the index](../README.md): L vendor documentation, release notes and
issue records; A anecdote or one uncontrolled report. Read 2026-10-01 against LiteLLM's documentation
and GitHub; the latest stable release that day was v1.103.2. Behaviour is per release: a verdict here
is what the documentation or a release note says, not a probe of the wire.

## 1. Routes and parameters (MONITOR)

- **Claude on Foundry.** The `azure_ai/` prefix (for example `azure_ai/claude-sonnet-5`) against
  `https://<resource>.services.ai.azure.com/anthropic`, to which LiteLLM appends `/v1/messages`.
  Listed parameters: `stream`, `stop`, `temperature`, `top_p`, `max_tokens`, `max_completion_tokens`,
  `tools`, `tool_choice`, `extra_headers`, `parallel_tool_calls`, `response_format`, `user`,
  `thinking`, `reasoning_effort`. "LiteLLM automatically passes max_tokens=4096 when no max_tokens
  are provided." Both `/chat/completions` and the native `/anthropic/v1/messages` endpoint serve it. L.
- **Dropped parameters.** `drop_params` drops OpenAI-standard parameters that the target provider
  does not support instead of failing; `additional_drop_params` names more, with JSONPath-like paths.
  It is set globally, per request, or in the proxy's `litellm_settings` or a model's
  `litellm_params`. L.
- **Provider-specific parameters pass through.** "LiteLLM treats any non-openai param, as a
  provider-specific param, and passes it to the provider in the request body, as a kwarg." A Claude
  parameter such as `output_config` therefore reaches the provider unless something else strips it.
  L.
- **Headers.** "By default, LiteLLM does not forward client headers to LLM provider APIs for security
  reasons." With `forward_client_headers_to_llm_api` set (in `general_settings` for all models, or
  under `litellm_settings: model_group_settings` for named models, wildcards or team aliases),
  headers starting with `x-` (not `x-stainless-*`) and `anthropic-beta` are forwarded. Without it, a
  client's `anthropic-beta` header never reaches the provider; a beta feature can instead ride the
  request body's `extra_headers`, a listed parameter on the Foundry route. L.
- **Effort.** One LiteLLM release refused `effort="max"` for Opus 4.7 on the client side, before the
  request reached Anthropic's API, because the value was hard-coded as Opus 4.6 only (issue #25957,
  opened 2026-04-17, closed by the stale bot as not planned on 2026-07-25). Whether current releases
  still refuse it is `UNVERIFIED`: probe before sending `max`. L.
- **Unknown parameters on other models.** Claude Code sending `output_config` to non-Anthropic models
  through the proxy failed with "Unknown parameter: output_config" (issue #22963, closed as completed
  2026-03-18). L.
- **Verbosity.** `text.verbosity` is forwarded to chat-completion providers from v1.93.0 (2026-07-19;
  PR #32254). L.

## 2. Prompt caching through the proxy (MONITOR)

- **Which routes.** LiteLLM documents prompt caching for `openai/`, `anthropic/`, `gemini/`,
  `vertex_ai/`, `bedrock/` (all three Bedrock forms), `deepseek/` and `xai/`; Claude-style
  `cache_control` blocks are translated across the Anthropic, Bedrock and Vertex routes. The Foundry
  `azure_ai/` page does not mention `cache_control`: a client's blocks may pass as provider-specific
  parameters, but probe before relying on them, and on the `"ttl": "1h"` field, which no LiteLLM page
  documents for that route. L.
- **Automatic injection.** v1.94.0 (2026-07-28) added an opt-in `enable_anthropic_prompt_caching`
  flag that injects breakpoints on the system prompt and the last turn "for Anthropic and Bedrock
  Claude models", standing down when the request already carries `cache_control` (PR #33573); the
  older `cache_control_injection_points` is set per model. Neither is documented for `azure_ai/`. L.
- **OpenAI keys.** `prompt_cache_key` and `prompt_cache_retention` pass for OpenAI routes. An Azure
  OpenAI caching failure specific to gpt-5.2 through the proxy, while direct calls cached, was fixed
  (issue #18219, closed 2025-12-29). Probe per model. L.
- **Usage fields.** Responses carry `cached_tokens`, `cache_creation_input_tokens` and
  `prompt_tokens_details`; a consumer has to read the creation count to see write costs. A
  `custom_openai` handler that drops `prompt_tokens_details` from the client response is open (issue
  #33967, opened 2026-07-20). L.
- **Pre-warming.** Because LiteLLM fills in `max_tokens=4096` when none is given, a `max_tokens: 0`
  pre-warm may not reach the provider as zero (inference from the documented default;
  `UNVERIFIED`).

## 3. Batches and compaction (MONITOR)

- **Batches.** The proxy's batches API covers OpenAI, Azure, Vertex, Bedrock, Mistral, vLLM and xAI,
  not Anthropic; Azure batches need a batch deployment on the Azure side. Automated batch cost
  tracking "requires a LiteLLM Enterprise license". Claude's Message Batches are not offered on
  Foundry at all ([azure-foundry.md](azure-foundry.md)). L.
- **Compaction.** A Claude compaction block in a response has no place in the OpenAI chat-completion
  shape, so it cannot round-trip through `/chat/completions`; the native `/anthropic/v1/messages`
  endpoint carries Claude's own shape (inference from the two formats).

## 4. Release notes worth knowing (VOLATILE)

- **v1.89.0** (2026-06-10): Claude Fable 5 support, first in v1.89.0-rc.2.
- **v1.93.0** (2026-07-19): GPT-5.6 Sol, Terra and Luna pricing and metadata, for OpenAI and Azure;
  verbosity forwarding.
- **v1.94.0** (2026-07-28): `enable_anthropic_prompt_caching`; Azure Anthropic `/messages` routed
  through the Rust core behind `rust: true`; a Cost Optimization page (beta) in the UI.
- **v1.95.0** (2026-08-03): Claude Opus 5; the native Anthropic `/v1/messages` route on the Rust
  gateway behind `LITELLM_RUST`.
- **v1.96.0** (2026-08-10): GPT-5.6 Terra and Luna prices adjusted to OpenAI's cut, and GPT-5.6
  prices corrected for OpenAI, Bedrock and long context. Releases before it carry GPT-5.6 prices from
  before the 2026-07-30 cut; explicit per-route prices in the proxy's configuration override the
  bundled map.
- **v1.103.2** (2026-10-01): the latest stable release that day; v1.104.0-rc.2 and a v1.105.0
  development build were also out.

## 5. Other gateways (VOLATILE)

- OpenRouter sometimes carries a model before its lab documents it: GLM-5.3-Prime (2026-09-23) was
  listed only there, with no Z.ai documentation page [glm-g12]; its models API lists what each route
  serves ([models.md](../models/cross-family.md#7-release-watch-volatile)). L.

## How to apply

1. Decide per feature whether it rides a parameter, a body field or a header, and enable header
   forwarding only for the model groups that need it (§1).
2. Probe every feature that matters on the exact gateway release and route, and read the cache usage
   fields there before estimating cost (§2).
3. Use the native `/anthropic/v1/messages` endpoint for Claude features with no OpenAI equivalent,
   such as compaction blocks (§3).
4. Pin the gateway release; check its prices against the provider's before relying on its cost
   reports (§4).

## Limits and open questions

- Nothing here was probed on the wire; the verdicts are documentation, release notes and issue
  records.
- LiteLLM's Foundry page is silent on `cache_control`, `output_config` and structured outputs; their
  behaviour on that route is `UNVERIFIED`.

## Sources

Read 2026-10-01: LiteLLM documentation: Azure Anthropic
<https://docs.litellm.ai/docs/providers/azure/azure_anthropic>; drop params
<https://docs.litellm.ai/docs/completion/drop_params>; provider-specific params
<https://docs.litellm.ai/docs/completion/provider_specific_params>; forwarding client headers
<https://docs.litellm.ai/docs/proxy/forward_client_headers>; prompt caching
<https://docs.litellm.ai/docs/completion/prompt_caching>; batches <https://docs.litellm.ai/docs/batches>;
release notes <https://docs.litellm.ai/release_notes>. GitHub, read through the API: releases
<https://github.com/BerriAI/litellm/releases> (v1.89.0, v1.93.0 to v1.96.0, the list to v1.103.2);
issues #25957, #22963, #18219, #14365 (a `prompt_cache_key` error calling Claude through Vertex from
Codex, closed 2026-02-13) and #33967; pull requests #32254 and #33573. Evidence record: [glm-g12].
