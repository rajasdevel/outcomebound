---
last_checked: 2026-10-01
volatility: VOLATILE (hosting split, feature lists, deployment types and meters move month to month)
sources:
  - https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry
  - https://platform.claude.com/docs/en/build-with-claude/overview
  - https://azure.microsoft.com/en-us/blog/claude-in-microsoft-foundry-is-now-generally-available/
  - https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability
  - https://azure.microsoft.com/blog/gpt-5-6-now-available-in-microsoft-foundry/
  - https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching
  - https://prices.azure.com/api/retail/prices
---

# Microsoft Foundry: model hosting and feature availability

Re-check before designing against a Foundry feature, deployment type or price.

How Claude and OpenAI's models are hosted on Microsoft Foundry, which features each hosting option
lacks, which deployment types the newest GPT models have, and what the meters say. For anyone who
reaches Claude or GPT through Foundry, directly or through a gateway. The other Claude cloud routes
are compared in [claude-cloud-platforms.md](claude-cloud-platforms.md); prompt caching on Azure
OpenAI is in [prompt-caching.md](../practices/prompt-caching.md) §4.

**Evidence classes**, as in [the index](../README.md): L lab or vendor documentation; A anecdote or
one uncontrolled report. Everything here is Anthropic's or Microsoft's documentation or price data,
read 2026-10-01 unless dated otherwise.

## 1. Claude on Foundry: two hosting options (VOLATILE)

Claude in Microsoft Foundry became generally available on 2026-06-29 (Microsoft's announcement). L.

| | Hosted on Azure | Hosted on Anthropic |
| --- | --- | --- |
| Where inference runs | Anthropic-operated service on Azure infrastructure; "prompts and completions remain within Azure", only usage metadata and content flagged by Anthropic's safety systems leave for Anthropic | Anthropic-operated service on Anthropic infrastructure |
| Models | Opus 5.5, Opus 5, Opus 4.8, Sonnet 5.5, Sonnet 5, Haiku 4.5 | every Claude model on Foundry, and the only option for Fable 5.1, Fable 5, the Mythos models, Opus 4.7, 4.6, 4.5 and Sonnet 4.6, 4.5 |
| Deployment types | Global Standard, US Data Zone Standard (Sonnet 5.5 Global only) | Global Standard |
| Recommended for | "Most workloads" | features or models not yet hosted on Azure |

- **Choose at deployment.** Each hosting option is a separate model version in the portal (for
  example version 1 hosted on Anthropic, version 2 on Azure); "Default settings" picks hosted on
  Azure where both exist. A deployment named `claude-opus-5` can therefore be either: check which
  before designing against a feature. Moving means creating a deployment of the other version and
  switching the deployment name.
- **Not supported when hosted on Azure** (400 by design): code execution; web search and web fetch
  versions later than `web_search_20250305` and `web_fetch_20250910` (so no dynamic filtering,
  response inclusion or cache bypass); Agent Skills; programmatic tool calling; the Files API. Claude
  Code detects an Azure-hosted deployment and adapts its feature set.
- **Not supported on Foundry under either hosting:** the Admin, Compliance and Models APIs, Message
  Batches, the advisor tool, Managed Agents, server-side fallback (use the client-side pattern),
  mid-conversation system messages, and the `computer_toolset_20260801` and
  `browser_toolset_20260801` toolsets; the skill version download endpoint is not supported.
- **Available on Foundry:** structured outputs, the 1M window on Fable 5.1, Fable 5, Opus 5.5 to 4.6,
  Sonnet 5.5, 5 and 4.6, tool search, and the MCP connector (beta). Threshold compaction and context
  editing are beta, as everywhere; a compaction block returned through a gateway's OpenAI-shaped
  endpoint does not survive the translation ([litellm.md](litellm.md)).
- **Billing and limits.** Billed through the Azure Marketplace in Claude Consumption Units, metered
  hourly and invoiced monthly in arrears, with no prepaid balance; Foundry returns none of Anthropic's
  `anthropic-ratelimit-*` headers; prompt caches are isolated per workspace.
- **SDKs.** Supported by the C#, Go, Java, PHP, Python and TypeScript SDKs; the Ruby SDK lacks native
  Foundry support.

## 2. GPT models on Foundry (VOLATILE)

- **Deployment types.** GPT-5.6 Sol, Terra and Luna launched on Foundry on 2026-07-09 in Global
  Standard, Data Zone Standard, Global Priority Processing and Global Provisioned (Microsoft's
  announcement). Microsoft's region table, updated 2026-09-04, lists gpt-6-astra (2026-09-03),
  gpt-6-sol and gpt-6-luna (2026-09-22) and gpt-6.1-sol (2026-09-29) under Global Standard beside
  them. L.
- **No batch deployment for the newest models.** The Global Batch and Data Zone Batch tables list
  nothing newer than gpt-5.4 and gpt-5.4-mini: no GPT-5.6 or GPT-6 model has a batch deployment type
  [as-of 2026-09-04, the page's update]. L.
- **Meters.** The Azure Retail Prices API carries meters for all three GPT-5.6 models, effective
  2026-08-01 (Terra, Luna) and 2026-09-01 (Sol). Global Standard, short context, per 1M tokens:
  Sol $4.00 input, $0.40 cached input, $5.00 cache write, $20.00 output; Terra $2.00, $0.20, $2.50,
  $12.00; Luna $0.20, $0.02, $0.25, $1.20. Data Zone meters are 1.1×, Priority Processing 2×, and the
  long-context meters 2× input and 1.5× output. L.
- **Sol's promotion.** Microsoft's launch post gave Sol $5.00/$30.00 and announces $4.00/$20.00 from
  2026-09-01 to 2026-11-30; Terra and Luna launched at $2.00/$12.00 and $0.20/$1.20. Sol's
  promotional price matches OpenAI's ([models.md](../models/openai/gpt-5.6-family.md#pricing-volatile)). L.
- **Caching.** Azure OpenAI's caching rules, including what PTU-M deployments lack, are in
  [prompt-caching.md](../practices/prompt-caching.md) §4.

## 3. Other models on Foundry

- xAI's documentation page for Grok on Microsoft Foundry still recommends think-mode prompting
  [grok-f11]; effort settings belong in configuration, not prose
  ([models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text)). L.

## How to apply

1. Record which hosting option each Claude deployment uses, and check a feature against §1 before
   designing against it.
2. Plan no batch workload on GPT-5.6 or GPT-6 through Foundry until a batch deployment type is listed
   (§2).
3. Price from the Retail Prices API meters for the deployment type in use, not from OpenAI's list
   (§2).

## Limits and open questions

- Default quotas for the GPT-5.6 models were not found in Microsoft's documentation.
- Meters were read for one region (eastus2) and spot-checked in others; prices can differ by region
  and change without notice.

## Sources

Read 2026-10-01: Anthropic, Claude in Microsoft Foundry
<https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry>, and features
overview <https://platform.claude.com/docs/en/build-with-claude/overview>; Microsoft, Claude in
Microsoft Foundry is now generally available, 2026-06-29
<https://azure.microsoft.com/en-us/blog/claude-in-microsoft-foundry-is-now-generally-available/>;
GPT-5.6 now available in Microsoft Foundry, 2026-07-09
<https://azure.microsoft.com/blog/gpt-5-6-now-available-in-microsoft-foundry/>; region availability for
Foundry Models sold by Azure, updated 2026-09-04
<https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability>
(standard and batch tabs); prompt caching with Azure OpenAI
<https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching>; Azure Retail Prices
API, `serviceName eq 'Foundry Models'`, meters containing "5.6"
<https://prices.azure.com/api/retail/prices>. Evidence record: [grok-f11].
