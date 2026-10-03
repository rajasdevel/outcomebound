# Research

Reference library of externally sourced facts and of OutcomeBound's own measured results, for the
agents and people who write, install and judge text that coding agents read: models, coding
harnesses, practices and providers. Dated research is context, not a rule: a design or a guide may
cite it by path, section and id, and the decision stays with the design or guide that makes it.

## Conventions

- Frontmatter on every document: `last_checked` (the day the whole document was verified),
  `volatility` (its dominant class, with the reason) and `sources` (the primary URLs).
- A claim inherits the document's `last_checked` unless it carries its own `[as-of YYYY-MM-DD]` tag
  or an evidence id that dates it. An own observation (O) of one repository's reviews, audits,
  ledgers or runs was made between August and October 2026; `last_checked` dates the re-reading of
  its record, not the observation.
- Volatility: **STABLE** (mechanics, method and measured studies; re-check at a model generation),
  **MONITOR** (features and limits; re-check about monthly or before designing against them),
  **VOLATILE** (prices, defaults, betas and open bugs; re-check before any load-bearing use). A
  section whose class differs from its document's says so in its heading.
- Each claim carries its evidence class and its source: a bracketed id into
  [`_evidence/`](_evidence/), a `[chk-…]` id, or a URL with the day it was read.
- When a document is re-verified, `last_checked` moves and every changed claim is rewritten in
  place; a claim that became false is deleted or rewritten, never followed by a correction.
- A reader finds a fact by its question in the tables below, then the document's key findings,
  then the section and the evidence id, then the record.

## Contents

### Models: one document per model or family

| Doc | Scope | Volatility | Checked | Re-check when |
| --- | --- | --- | --- | --- |
| [models/alibaba/qwen.md](models/alibaba/qwen.md) | Alibaba Qwen | VOLATILE | 2026-09-25 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/anthropic/claude-5-family-prompting.md](models/anthropic/claude-5-family-prompting.md) | Claude 5 generation: prompting shared across Fable, Opus and Sonnet | MONITOR | 2026-10-01 | the lab ships a model or a prompting page for this family |
| [models/anthropic/earlier-generations.md](models/anthropic/earlier-generations.md) | Claude before the 5 generation: Claude 3.7 Sonnet to Opus 4.8 | STABLE | 2026-09-25 | a correction to the history it records |
| [models/anthropic/fable.md](models/anthropic/fable.md) | Claude Fable 5 and 5.1 (and Mythos 5, 5.1) | MONITOR | 2026-10-01 | the lab ships a model or a prompting page for this family |
| [models/anthropic/haiku.md](models/anthropic/haiku.md) | Claude Haiku | VOLATILE | 2026-10-01 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/anthropic/opus.md](models/anthropic/opus.md) | Claude Opus 5 and 5.5 | MONITOR | 2026-10-01 | the lab ships a model or a prompting page for this family |
| [models/anthropic/sonnet.md](models/anthropic/sonnet.md) | Claude Sonnet 5 and 5.5 | MONITOR | 2026-10-01 | the lab ships a model or a prompting page for this family |
| [models/cross-family.md](models/cross-family.md) | Models across families: direction of travel, divergences and forecasts | MONITOR | 2026-09-25 | a tracked lab ships a model or a prompting page, or a forecast's horizon passes |
| [models/deepseek/deepseek.md](models/deepseek/deepseek.md) | DeepSeek | VOLATILE | 2026-09-25 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/google/gemini.md](models/google/gemini.md) | Google Gemini (and Gemma) | VOLATILE | 2026-09-25 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/meta/muse-spark.md](models/meta/muse-spark.md) | Meta Muse Spark | MONITOR | 2026-09-25 | the lab ships a model or a prompting page for this family |
| [models/minimax/minimax.md](models/minimax/minimax.md) | MiniMax | MONITOR | 2026-09-25 | the lab ships a model or a prompting page for this family |
| [models/mistral/mistral.md](models/mistral/mistral.md) | Mistral | MONITOR | 2026-09-25 | the lab ships a model or a prompting page for this family |
| [models/moonshot/kimi.md](models/moonshot/kimi.md) | Moonshot Kimi | VOLATILE | 2026-09-25 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/openai/earlier-generations.md](models/openai/earlier-generations.md) | OpenAI before GPT-5.6: GPT-4.1 to GPT-5.5, the Codex models and gpt-oss | STABLE | 2026-09-25 | a correction to the history it records |
| [models/openai/gpt-5.6-family.md](models/openai/gpt-5.6-family.md) | OpenAI GPT-5.6: Sol, Terra and Luna | VOLATILE | 2026-10-01 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/openai/gpt-6-family.md](models/openai/gpt-6-family.md) | OpenAI GPT-6: Astra, Sol, Luna and 6.1 Sol | VOLATILE | 2026-10-01 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/other/open-weight-labs.md](models/other/open-weight-labs.md) | Open-weight labs: shared direction, NVIDIA Nemotron, Tencent Hy, Xiaomi MiMo | MONITOR | 2026-09-25 | the lab ships a model or a prompting page for this family |
| [models/xai/grok.md](models/xai/grok.md) | xAI Grok (xAI now operating as SpaceXAI) | VOLATILE | 2026-09-25 | the lab ships a model, changes a price or default, or a quarter passes |
| [models/zai/glm.md](models/zai/glm.md) | Z.ai GLM | VOLATILE | 2026-09-25 | the lab ships a model, changes a price or default, or a quarter passes |

### Coding harnesses: one document per harness

| Doc | Scope | Volatility | Checked | Re-check when |
| --- | --- | --- | --- | --- |
| [harnesses/amp.md](harnesses/amp.md) | Amp | VOLATILE | 2026-09-25 | Amp changes which instruction files it reads, where it finds skills, its plugin |
| [harnesses/claude-code.md](harnesses/claude-code.md) | Claude Code | VOLATILE | 2026-09-25 | a Claude Code release changes how it loads `CLAUDE.md` or `AGENTS.md`, caps or |
| [harnesses/codex.md](harnesses/codex.md) | Codex (CLI and app) | VOLATILE | 2026-09-25 | a Codex release changes how it loads `AGENTS.md`, caps the chain, runs hooks, gates |
| [harnesses/cross-harness.md](harnesses/cross-harness.md) | Coding harnesses compared: what they load, cap, compact and run | VOLATILE | 2026-09-25 | a harness release changes how it loads, caps or compacts instruction files, runs hooks |
| [harnesses/cursor.md](harnesses/cursor.md) | Cursor | VOLATILE | 2026-09-25 | a Cursor release changes how it reads rules, `AGENTS.md` or `CLAUDE.md`, runs hooks |
| [harnesses/gemini-cli.md](harnesses/gemini-cli.md) | Gemini CLI | VOLATILE | 2026-09-25 | a Gemini CLI release changes which context files it loads, how its system prompt |
| [harnesses/others.md](harnesses/others.md) | Other coding harnesses | VOLATILE | 2026-09-25 | a harness's entry when it releases a change to how it loads instruction files, caps them, |
| [harnesses/pi.md](harnesses/pi.md) | Pi | VOLATILE | 2026-09-25 | Pi changes which context files it reads, what project trust gates, its extension |

### Practices

| Doc | Scope | Volatility | Checked | Re-check when |
| --- | --- | --- | --- | --- |
| [practices/agent-authorization.md](practices/agent-authorization.md) | Agent authorization: what lets an agent act | MONITOR | 2026-10-01 | Claude Code or Codex changes its permission modes, classifier rules or reviewer; a |
| [practices/agent-evals.md](practices/agent-evals.md) | Evaluating agent systems: suites, statistics, error analysis, SQL correctness | STABLE | 2026-10-01 | an evaluation tool changes what it ships, a lab revises its agent-eval guidance, or |
| [practices/agent-memory.md](practices/agent-memory.md) | Agent memory | MONITOR | 2026-10-01 | a harness changes where or how it keeps memory, a memory product changes what it |
| [practices/agent-workspace.md](practices/agent-workspace.md) | Agent workspace and long runs | STABLE | 2026-09-29 | a harness changes where it places, sweeps or isolates worktrees, how it stores |
| [practices/cli-conventions.md](practices/cli-conventions.md) | Check commands and CLI conventions | STABLE | 2026-09-22 | a surveyed tool changes its doctor or check command, or a guidance page (clig.dev, |
| [practices/evaluations.md](practices/evaluations.md) | Evaluating what model-facing text changes in a coding agent's work | STABLE | 2026-10-01 | a pass runs on another model or codex release, the runner or a fixture changes, or |
| [practices/git.md](practices/git.md) | Git behaviour that tools rely on | STABLE | 2026-10-01 | a Git release changes porcelain output, archive headers, `ls-tree` path handling, |
| [practices/llm-as-judge.md](practices/llm-as-judge.md) | Model judges: validity, biases, prompting, calibration, consistency | STABLE | 2026-10-01 | a study measures how a judge's reasoning effort changes its accuracy, a judge model |
| [practices/long-context-and-compaction.md](practices/long-context-and-compaction.md) | Long context and compaction | STABLE | 2026-10-01 | a provider changes its windows or compaction API, a harness changes how it compacts, |
| [practices/prompt-caching.md](practices/prompt-caching.md) | Prompt caching | VOLATILE | 2026-10-01 | a provider changes its caching rules, minimums, lifetimes or prices, or a model |
| [practices/quality-floor.md](practices/quality-floor.md) | Quality floors: format, lint, type, secret and shell checks as a gate | STABLE | 2026-09-13 | a tool named in §8 or §11 ships a new major or minor version, or a floor is fitted to |
| [practices/releasing.md](practices/releasing.md) | Packaging and releasing a command-line tool | STABLE | 2026-10-01 | a new major version of `actions/checkout` or `actions/setup-python`, a change to |
| [practices/review.md](practices/review.md) | Independent review of agent work | MONITOR | 2026-10-01 | a lab changes its guidance on fresh-context verifiers or code review, a study compares |
| [practices/simplified-technical-english.md](practices/simplified-technical-english.md) | ASD-STE100 Simplified Technical English and text for coding agents | STABLE | 2026-10-03 | ASD publishes Issue 10, or a measured study of a controlled language in prompts for models |
| [practices/skills.md](practices/skills.md) | Agent skills: what works, what they are for, and the public sets compared | MONITOR | 2026-10-01 | a harness changes how it lists or truncates skills, or one of the public sets ships a |
| [practices/summarization-layers.md](practices/summarization-layers.md) | Summaries, summary layers and citations | STABLE | 2026-10-01 | a study measures drift level by level in a summary hierarchy, compares small with |
| [practices/testing.md](practices/testing.md) | Tests worth keeping | STABLE | 2026-10-01 | pytest, Python or GitHub Actions changes a default named in §4, or the audited suite |
| [practices/ticket-tracking.md](practices/ticket-tracking.md) | Tickets on a tracker: acceptance, evidence and landing | STABLE | 2026-10-01 | `gh` or GitHub's GraphQL schema changes the fields or relations a reader uses, a |
| [practices/work-breakdown.md](practices/work-breakdown.md) | Work breakdown for coding agents | STABLE | 2026-09-26 | METR or another evaluator publishes a horizon for a new model, a lab or harness |
| [practices/writing-for-models.md](practices/writing-for-models.md) | Writing for models: instruction files, skills, briefs and tool output | MONITOR | 2026-09-25 | a tracked lab or harness ships a model, a prompting guide or a change to what it |

### Providers and routes

| Doc | Scope | Volatility | Checked | Re-check when |
| --- | --- | --- | --- | --- |
| [providers/azure-foundry.md](providers/azure-foundry.md) | Microsoft Foundry: model hosting and feature availability | VOLATILE | 2026-10-01 | before designing against a Foundry feature, deployment type or price |
| [providers/claude-cloud-platforms.md](providers/claude-cloud-platforms.md) | Claude on cloud platforms | VOLATILE | 2026-10-01 | before designing against a feature on a cloud route, and whenever Anthropic's features |
| [providers/litellm.md](providers/litellm.md) | LiteLLM and other gateways: what passes through | MONITOR | 2026-10-01 | before upgrading a gateway or relying on a new parameter passing through it |

## Evidence

[`_evidence/`](_evidence/) holds every record the sweeps produced, one JSON object a line, keyed by
an `id` that the references cite in brackets: `2026-09-25.jsonl` (the writing, models, harnesses
and skills sweeps) and `2026-09-26.jsonl` (the work-breakdown sweep). Each record keeps the claim
as verified, a verbatim quote, its URL and date, the verification verdict (`supported` or
`overstated`, with the first wording kept where the fact-check rewrote it), its evidence class and,
on most records, the sweep reader's note, which was not itself fact-checked.
`2026-09-25-sources.json` lists the 583 sources the 2026-09-25 sweeps read and the 64 pages that
were unreachable or read only in part, each with what was read instead.
[practices/writing-for-models.md](practices/writing-for-models.md) §1 describes the fields in full. Id prefixes name
their sweep (`anthropic-`, `openai-`, `claude-`, `harness-loading-coverage-` and the other
practice, family and finding prefixes are in `2026-09-25.jsonl`; `sizing-` ids, with three
re-verified records, are in `2026-09-26.jsonl`). Facts checked at their source after the sweeps
are cited as `[chk-…]` ids or as a URL with its read date, listed under each reference's Sources.

Evidence classes, as the references label them:

- **measured** (M): an experiment, benchmark or counted observation;
- **lab-guidance** (L): a model lab's or tool vendor's own documentation or guidance;
- **practitioner-consensus** (P): several independent practitioners agreeing;
- **anecdote** (A): one person's account;
- **standards** (S): a standards body's text;
- **forecast** (F): a prediction, held with its falsifier and horizon;
- **own result** (O): a result recorded in this project's own runs or audits.

## How the research is done

1. **Sweeps.** Readers work in parallel, one per topic or model family, reading primary sources:
   lab guidance and release posts, model cards, API docs and changelogs, harness docs and source,
   papers, standards, practitioners. Each finding is recorded with its claim, a verbatim quote, the
   URL, the date, the source type, an evidence class and a stance.
2. **Fact-check.** An independent pass re-reads every source against its record and gives one of
   three verdicts: supported, overstated (the claim corrected, the first wording kept), or dropped.
   It also checks that a cited source is its current revision, not only that it exists: one
   citation check found a standard cited at a superseded revision, and an inactivated predecessor
   that had to be kept out (A, one review, 2026-09).
3. **Completeness.** A critic reads the first synthesis for what it missed, and each gap it names
   is swept in turn.
4. **Synthesis.** The records are distilled into the references, each claim labelled with its
   evidence class and, where it matters, the models and reader tiers it covers.
5. **Adversarial critique.** An independent reviewer attacks each synthesis; it is revised, and
   disputed facts are re-checked at their source.

## Keeping it current

Each reference is edited in place when its evidence changes, and Git holds every earlier version.
A claim found false is rewritten or deleted where it stands, never followed by a correction; a
ledger record keeps its first wording in `original_claim`.
A reference's "Limits and open questions" names what would change it and when to look again:
forecasts carry their horizons in [models/cross-family.md](models/cross-family.md), and harness facts carry the day they
were read, as `adapters/harnesses.json` rows carry `verified_on` and `recheck_on`.

Refresh a reference when a model or harness release it covers changes how text is loaded, capped
or followed; when a lab publishes new prompting guidance; when a forecast's horizon passes (score
it held, falsified or unscored); or when a quarter has passed since it was checked. New records go
into `_evidence/<date>.jsonl` through the same fact-check; an id names one finding across all
evidence files, a later file repeats an id only to re-verify that finding and says so in the record,
and a new sweep continues each prefix's numbering from the highest id in any file.
