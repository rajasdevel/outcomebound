---
last_checked: 2026-10-01
volatility: VOLATILE (feature availability per platform changes with each release; the operator split is stable)
sources:
  - https://platform.claude.com/docs/en/build-with-claude/overview
  - https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock
  - https://platform.claude.com/docs/en/build-with-claude/claude-platform-on-aws
  - https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai
  - https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry
  - https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages
  - https://platform.claude.com/docs/en/build-with-claude/prompt-caching
---

# Claude on cloud platforms

Re-check before designing against a feature on a cloud route, and whenever Anthropic's features
overview or a platform page changes.

What changes when Claude is reached through Amazon Bedrock, Claude Platform on AWS, Google Cloud's
Agent Platform (formerly Vertex AI) or Microsoft Foundry instead of the Claude API: who operates the
inference, which features each route lacks, how caching and endpoints differ, and what harnesses do on
each. For anyone who chooses a route for Claude or relies on a feature through one. Microsoft Foundry,
which also serves OpenAI's models, has its own file, [azure-foundry.md](azure-foundry.md); gateways in
front of any of these are in [litellm.md](litellm.md).

**Evidence classes**, as in [the index](../README.md): L lab or vendor documentation; A anecdote or
one uncontrolled report; O own result. Everything here is Anthropic's or the platform's documentation
of its own product, read 2026-10-01 unless dated otherwise. Bracketed ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).

## 1. Who operates what (MONITOR)

| Route | Operator of inference | Billing | API surface |
| --- | --- | --- | --- |
| Claude API | Anthropic | Anthropic | `/v1/…` |
| Claude Platform on AWS | Anthropic, on AWS infrastructure (workspaces created from 2026-09-18; earlier ones may run outside AWS) | AWS Marketplace | the Claude API unchanged, at `aws-external-anthropic.{region}.api.aws`, with an `anthropic-workspace-id` header; SigV4 or API key |
| Claude in Amazon Bedrock (Opus 4.7 and later) | AWS, "zero operator access" for Anthropic | AWS | Messages API at `bedrock-mantle.{region}.api.aws/anthropic/v1/messages`; model ids carry an `anthropic.` prefix. The older `InvokeModel`/`Converse` integration remains for Opus 4.6 and earlier |
| Google Cloud Agent Platform | Google | Google Cloud | Messages API with `model` in the URL and `anthropic_version: vertex-2023-10-16` in the body |
| Microsoft Foundry | Anthropic, on Azure or on Anthropic infrastructure by hosting option | Azure Marketplace, in Claude Consumption Units | `{resource}.services.ai.azure.com/anthropic/v1/*`; [azure-foundry.md](azure-foundry.md) |

New models "typically launch on Claude Platform on AWS the same day as the first-party Claude API";
features and beta headers on Bedrock follow Amazon's own releases. L.

## 2. Features each route lacks (VOLATILE)

From Anthropic's features overview and the platform pages, read 2026-10-01. L.

- **Not on Bedrock:** Message Batches, Files API and URL sources, server-side tools (code execution,
  web search, web fetch, advisor), Agent Skills, the MCP connector, programmatic tool calling, the
  Models, Admin, Compliance and Usage and Cost APIs, Managed Agents, server-side fallback, and the
  `computer_toolset_20260801`/`browser_toolset_20260801` toolsets (the beta computer-use versions
  remain). The Bedrock page lists structured outputs as not supported while the features overview
  marks them available on Bedrock: probe before relying on them.
- **Not on Google Cloud:** Message Batches, Files API and URL sources, code execution, web fetch,
  the advisor, Agent Skills, the MCP connector, programmatic tool calling, the Models, Admin,
  Compliance and Usage and Cost APIs, Managed Agents and server-side fallback. Web search, structured
  outputs and the browser-use tool are available. Requests are limited to 30 MB.
- **Not on Claude Platform on AWS:** fast mode, OAuth, OpenAI-compatible endpoints, HIPAA readiness,
  some Admin API workspace and key endpoints, workspace member management, and the Claude Code
  workspace and Analytics API. Batches, Files API, Agent Skills and code execution are available.
- **Not on Microsoft Foundry:** see [azure-foundry.md](azure-foundry.md) §1.
- **Beta everywhere it exists:** threshold compaction and context editing are beta on all five routes;
  fallback credit is beta on all five; server-side fallback is a Claude API beta only; on-demand
  compaction (`compact-2026-09-04`) is not available on Bedrock (as read for
  [long-context-and-compaction.md](../practices/long-context-and-compaction.md)).
- **Data residency.** `inference_geo` exists on the Claude API and Claude Platform on AWS. Bedrock
  and Google Cloud offer global endpoints with no premium and regional (and on Google Cloud
  multi-region `us`/`eu`) endpoints at a 10% premium; on Google Cloud, specific regional endpoints
  serve Sonnet 4.6 and earlier, newer models the global or multi-region ones; provisioned
  throughput needs a regional endpoint.
- **Mid-conversation system messages** are available on the Claude API, Bedrock and Google Cloud,
  not on Microsoft Foundry.
- **Rate-limit headers.** Foundry returns none of Anthropic's `anthropic-ratelimit-*` headers.

## 3. Caching on each route (VOLATILE)

- The minimum cacheable prompt lengths of the Claude API hold on Claude Platform on AWS, Google Cloud
  and Microsoft Foundry; Bedrock documents its own minimums, failure behaviour and usage field names.
  L.
- Caches are isolated per workspace on the Claude API, Claude Platform on AWS and Microsoft Foundry,
  and per organization on Bedrock and Google Cloud. L.
- The `usage` object is the same on every route. L.
- The rest of caching, per provider, is in
  [prompt-caching.md](../practices/prompt-caching.md).

## 4. Harnesses on cloud routes (VOLATILE)

- **Claude Code versions.** Use Claude Code 2.1.255 or later with Claude Fable 5.1 on Bedrock, and
  2.1.280 or later with Claude Opus 5.5. L.
- **Auto mode.** On Bedrock, Google Cloud's Agent Platform and Foundry, Claude Code's auto mode
  supports only Sonnet 5 or later, Opus 4.7 or later and the Fable models
  ([agent-authorization.md](../practices/agent-authorization.md)). L.
- **Instruction files.** Before Claude Code 2.1.281 some sessions, Bedrock among them, could not read
  `AGENTS.md` at all ([harnesses.md](../harnesses/claude-code.md#1-instruction-files-and-precedence)). L.
- **Endpoint and credential settings.** Claude Code's `env.ANTHROPIC_BEDROCK_BASE_URL` and
  `env.ANTHROPIC_VERTEX_BASE_URL`, and the `awsAuthRefresh`, `awsCredentialExport` and
  `gcpAuthRefresh` settings that run a command, are among the configuration keys that redirect
  traffic or execute code ([harnesses.md](../harnesses/cross-harness.md#94-configuration-keys-that-execute-code-or-widen-permissions)). L.
- **Availability of new models.** Sonnet 5.5 was generally available on the Claude API, Bedrock,
  Google Cloud, Microsoft Foundry and Claude Platform on AWS from its release on 2026-09-28
  ([models.md](../models/cross-family.md#8-forecasts), forecast A1a). L.
- **A cloud route can lag the provider.** One team saw a cloud provider's route for a newly launched
  model family report no cache reads at all until the provider fixed it (A [as-of 2026-07], not
  re-checked). Probe each feature on the route actually used.

## How to apply

1. Before designing against a feature, find it in Anthropic's features overview for the route in use,
   and probe it where the overview and the platform page disagree (§2).
2. Choose Claude Platform on AWS over Bedrock where same-day features, batches, Files or Skills
   matter and Anthropic operating the inference is acceptable; Bedrock where AWS must operate it (§1,
   §2).
3. Read the cache fields on the route actually used before estimating cost (§3).

## Limits and open questions

- Platform pages and the features overview disagree in places (structured outputs on Bedrock);
  neither was probed here.
- Lifecycle dates on partner-operated platforms are set by the partner and can differ from the Claude
  API's.

## Sources

Read 2026-10-01: Anthropic, features overview
<https://platform.claude.com/docs/en/build-with-claude/overview>; Claude in Amazon Bedrock
<https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock>; Claude Platform on
AWS <https://platform.claude.com/docs/en/build-with-claude/claude-platform-on-aws>; Claude on Google
Cloud <https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai>; Claude in Microsoft
Foundry <https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry>;
mid-conversation system messages
<https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages>; prompt
caching <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>.
