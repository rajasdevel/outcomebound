---
last_checked: 2026-10-01
volatility: MONITOR (classifier tuning, refusal billing and availability changed several times in 2026)
sources:
  - https://platform.claude.com/docs/en/models/fable-5-1/overview
  - https://platform.claude.com/docs/en/models/fable-5-1/whats-new-fable-5-1
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1
  - https://platform.claude.com/docs/en/models/fable-5/overview
  - https://platform.claude.com/docs/en/models/fable-5/introducing-claude-fable-5-and-claude-mythos-5
  - https://platform.claude.com/docs/en/models/fable-5/migration-guide
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
  - https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback
  - https://www.anthropic.com/news/redeploying-fable-5
  - https://www.anthropic.com/news/claude-fable-5-mythos-5
---

# Claude Fable 5 and 5.1 (and Mythos 5, 5.1)

What Anthropic's Fable models are, what their API accepts and rejects, how they behave, how
Anthropic says to prompt them, what their refusals and caching cost, and how they reached their
current state. For anyone choosing Fable for long-horizon work or writing text it will read.
What every Claude 5 model shares is in [claude-5-family-prompting.md](claude-5-family-prompting.md);
labels and ids as in [../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and availability (VOLATILE)

- **The tier.** Anthropic introduced Fable 5 as "a Mythos-class model that we've made safe for
  general use", the Mythos class sitting above Opus. Mythos 5 is the same model without the safety
  classifiers, for Project Glasswing partners (defensive cybersecurity), and succeeds Mythos
  Preview; a planned programme would lift the biology and chemistry safeguards for selected
  researchers [chk-claude-pages].
- **Fable 5.1** (`claude-fable-5-1`, 2026-09-01, "Latest") succeeds Fable 5 for long-running
  agentic coding, knowledge work and research; Mythos 5.1 offers the same capabilities to Glasswing
  participants only. Anthropic's own advice: start most workloads on Opus, and use Fable 5.1 for
  demanding reasoning and long-horizon agentic work, or when evaluations on Opus at higher effort
  still fall short. Comparative latency: "Slower" [claude-g12].
- **Fable 5** (`claude-fable-5`, 2026-06-09) is legacy since 5.1, retirement not sooner than
  2027-06-09; Fable 5.1's not sooner than 2027-09-01.
- **Specifications, both.** 1M-token window (default and maximum, standard price across it), 128K
  output, text and images in, Opus 4.7's tokenizer (token counts unchanged between them and Mythos
  Preview). Knowledge cutoff Jan 2026 (Fable 5), Jun 2026 (Fable 5.1).
- **Platforms.** Claude API, Amazon Bedrock (`anthropic.claude-fable-5-1`), Google Cloud,
  Microsoft Foundry and Claude Platform on AWS.
- **Data retention.** Both require 30-day data retention and are not available under zero data
  retention unless Anthropic expressly authorizes it; on the Claude API a request from an
  organization whose retention does not meet this returns 400 `invalid_request_error`. Both are
  designated Covered Models.
- **Content provenance (5.1).** Text from Fable 5.1 and Mythos 5.1 carries Anthropic's statistical
  text watermark on every platform; supported image, video and audio files produced through code
  execution carry C2PA Content Credentials when retrieved through the Files API.

### Availability history (MONITOR)

- Released 2026-06-09. On Friday 2026-06-12 the US government applied export controls to Fable 5
  and Mythos 5, after a report in which Amazon researchers found a way of bypassing Fable 5's
  safeguards to have it identify software vulnerabilities; Anthropic found that less capable models
  (Opus 4.8, GPT-5.5, Kimi K2.7) could identify the same vulnerabilities.
- Mythos 5 access was restored for a set of US organizations after government approval on
  2026-06-26; the controls were lifted on 2026-06-30, and Fable 5 returned to all users on
  2026-07-01 with a new cyber classifier that blocks the reported technique "in over 99% of cases"
  at the cost of "flagging benign requests more often during routine coding and debugging tasks".
  In Anthropic's apps a blocked Fable 5 request is sent to Opus 4.8 instead, with a notice.
- What follows for a harness: availability of a primary model is not guaranteed; keep a fallback
  across models healthy (inference).

## API surface (STABLE)

- **Thinking always on.** Omit `thinking` or send `{"type": "adaptive"}`. `thinking: {"type":
  "disabled"}` and manual extended thinking (`budget_tokens`) return 400 at any effort. Depth is
  set by `output_config.effort` (`low`, `medium`, `high`, `xhigh`, `max`; default `high`).
- **Thinking output.** The raw chain of thought is never returned; `display: "summarized"` returns
  a readable summary; the default `"omitted"` returns blocks with an empty `thinking` field. Pass
  thinking blocks back complete and unmodified: edited, reordered or partly dropped blocks return
  400. Select content blocks by `type`, never by position.
- **Rejected:** prefill (400), non-default `temperature`, `top_p`, `top_k` (400). On Fable 5.1 and
  Mythos 5.1 also forced `tool_choice` (`any` or `tool`, 400; `auto` and `none` unchanged): thinking
  is always on and a forced call would skip it, so the model would write its working into the tool
  arguments. For schema-valid JSON use strict tool use or structured outputs (`output_config.format`);
  to have the model call a tool, say in the prompt when it applies, which Fable 5.1 "follows
  reliably".
- **Thinking blocks (5.1).** Fable 5.1 reads earlier models' blocks; no earlier model reads its
  blocks, and the API drops one replayed to an earlier model, unbilled and, without the
  `thinking-binding-controls-2026-08-01` beta, silently. On the Claude API, Fable 5.1 and Mythos 5.1
  read Opus 5.5's blocks. For accounts created on or after 2026-08-31 the API checks that nothing
  before a block changed (system prompt, tools, earlier messages, or the bytes behind an image or
  document URL) and returns 400 ("The block is bound to a different conversation"); older accounts
  are checked only when the request sets `thinking.block_binding.prefix_mismatch_behavior`.
  Removing a leading run of blocks, server-side compaction or context editing, moving
  `cache_control` and changing effort keep later blocks valid. Mythos 5.1 does not run the check.
- **New on 5.1 (beta):** per-message effort (`mid-conversation-output-config-2026-07-01`; Claude API
  and Google Cloud); turn-scoped system messages (`clear_at: "next_user_message"`,
  `mid-conversation-system-clear-at-2026-08-21`), which render for one turn, cost nothing once
  cleared and keep the cache and later thinking blocks valid; `display: "updates"`
  (`thinking-display-updates-2026-08-18`), which returns the short progress updates written between
  tool calls as text while reasoning stays hidden.
- **Supported features** (Fable 5): effort, task budgets (beta), the memory tool, code execution,
  programmatic tool calling, tool-result clearing through context editing (beta), compaction,
  vision; mid-conversation system messages and tool changes.

## Refusals and fallback (MONITOR)

- **Classifiers.** Fable 5 runs classifiers aimed at offensive cybersecurity techniques (exploits,
  malware, attack tooling), biology and life-sciences content (lab methods, molecular mechanisms),
  and extraction of its summarized thinking; benign security and life-sciences work can trip them.
  Fable 5.1 covers the same `stop_details` categories, with fewer false positives than Fable 5 at
  launch, and permits finding vulnerabilities in source code [chk-claude-pages].
- **Shape and billing.** See the shared section of
  [claude-5-family-prompting.md](claude-5-family-prompting.md#shared-api-behaviour-volatile): a
  decline is HTTP 200 with `stop_reason: "refusal"`; since 2026-09-24 a pre-output decline in
  `bio`, `frontier_llm` or `reasoning_extraction` is billed (earlier, pre-output declines were not
  billed); mid-stream declines bill input and streamed output; monitoring built on error rates never
  sees a decline.
- **Fallback targets.** The Fable 5 guide names Opus 4.8 as the fallback; Anthropic's Fable page now
  routes biology flags to Opus 5; the permitted fallback targets for Fable 5.1 are Opus 4.8 and Opus
  5 [chk-claude-pages]. `fallbacks: "default"` does not retry a `reasoning_extraction` decline.
- **Fewer false positives on 5.1** (Fable 5.1 guide): ask "Are there any bugs in this program?"
  rather than "Does this program compile without errors?"; give context (or documentation) for a
  lesser-known programming language; remove tools that return base64-encoded data into the context.

## Behaviour (MONITOR)

Fable 5, from its guide, compared with Opus 4.8:
- Sustains multiday, goal-directed runs; first-shot correctness on complex, well-specified problems;
  higher bug-finding recall outside the classifier domains; uses bash and crop tools on flipped,
  blurry or noisy images; dispatches parallel subagents more readily and sustains them.
- **Longer turns.** Single requests on hard tasks can run for many minutes at higher effort and
  autonomous runs for hours: adjust timeouts, streaming and progress indicators, and consider
  checking on runs asynchronously. Anthropic's line against overplanning: "When you have enough
  information to act, act…".
- At higher effort on routine work it can gather context and deliberate beyond the need, and tidy or
  refactor unasked; Anthropic gives a scope block against features, refactors and abstractions the
  task does not require.
- Occasionally takes unrequested actions (drafting an email nobody asked for, defensive git-branch
  backups): state what it should and should not do.

Fable 5.1, from its what's-new page, compared with Fable 5 (each with a prompting fix in its guide):
- **Parallel tool calling is more variable:** one call per turn in long loops where the next reads
  are only implied (custom coding agents, bash-and-editor harnesses, computer use); answer quality
  unchanged, cost and wall-clock up.
- **Fewer progress updates** between tool calls, especially at higher effort [claude-f19].
- **Answers from memory more often at `low` effort**, calling search less [claude-g12].
- **Denser prose** in places; **less formatting** in chat (bold, headers, lists), so anti-formatting
  rules written for older models can suppress structure the content needs [claude-f20].
- **Unmarked quotations** in summaries of sources; **whole-file rewrites** for small edits.
- May stop early unless told it runs autonomously; adds unrequested fixes and tests unless told to
  keep extras out [claude-g12].
- Gains over Fable 5 are widest at higher effort: long agentic coding, documents, spreadsheets and
  slides, multistep research, vision with crop-and-zoom, long context, computer use; multilingual on
  par.

METR judged Opus 5.5 an incremental, on-trend step over Fable 5.1 [claude-trend]; customers
described overnight 18- to 38-hour unattended runs on Opus 5.5 and Fable 5.1 [claude-trend]. Fable
5.1 shifted behaviour relative to Fable 5 [measured-f25].

## Prompting (MONITOR)

Fable 5 (its guide; the patterns most often needing tuning):
- One brief principle replaces an enumerated list: "A short brevity instruction is as effective as
  listing each pattern" ("Lead with the outcome…"); likewise one checkpoint rule: "Pause for the
  user only when the work genuinely requires them: a destructive or irreversible action, a real
  scope change, or input that only they can provide" [claude-f17].
- Ground progress claims in tool results; state the boundaries; build a memory surface; give the
  reason; add the autonomous-run reminder; avoid context countdowns (all in
  [claude-5-family-prompting.md](claude-5-family-prompting.md#standing-guidance-monitor)).
- **Subagents.** Use them often, say when delegation fits, prefer asynchronous communication; long-
  lived subagents that keep their context save time and cost through cache reads.
- **Readability.** In long agentic sessions it can write dense arrow-chain shorthand and refer to
  thinking the user never saw; Anthropic's addendum asks for a final message written as a
  re-grounding, outcome first, in complete sentences.
- **Send-to-user tool.** For long asynchronous agents, a client tool whose input is displayed
  verbatim without ending the turn; the model rarely calls it without an instruction to.
- **Scaffolding changes.** Start at the top of your difficulty range; make self-verification
  explicit in long-run prompts, since "separate, fresh-context verifier subagents tend to outperform
  self-critique" (this conflicts with the Opus 5 guide's advice to remove verification
  instructions; each holds for its own model) [claude-f14]; refactor prompts and skills written for
  older models; do not ask it to reproduce its reasoning.

Fable 5.1 (its guide): existing Fable 5 prompts "should perform well without changes". Adjustments:
- Re-run the effort sweep; at `medium` results roughly match Fable 5 at lower cost, and at `low` it
  is "often competitive with Claude Opus and Claude Sonnet models on cost per task while scoring
  higher".
- Progress updates: first set `display: "updates"`, then remove lines such as "hold all findings for
  the final response", then ask for the updates you want; if the product hides tool output, say so.
- Append a one-sentence batching nudge after each set of tool results, as a turn-scoped system
  message, leaving earlier copies untouched.
- Keep history append-only; if you compact on the client, replace the history with one summary
  message plus the new turn; with cheaper cache reads, compacting early to save cost may no longer
  pay, so try later compaction points.
- Writing density: define the anti-pattern (mannered prose). Formatting: replace anti-formatting
  rules with a rule for when formatting fits. Quotation: give one complete worked example.
- **Finish the whole task:** two system-prompt additions, the first beginning by telling the model
  the user is not watching ("carries much of the effect"), the second defining the request as the
  scope of the deliverable; the first can make it ask less about ambiguous requests.
- Tell it what a client-side compaction summary must keep; leave out unrequested changes and tests;
  for search at `low` effort, say that recognizing a name is not knowing its current state; prefer
  targeted edits.
- At `xhigh` and `max` it can draft a long deliverable in its thinking and write it again: run such
  requests at `high`, or leave room in `max_tokens` and append the guide's note.
- Let the lead agent keep working while subagents run (tools that return at once, results delivered
  later, a separate wait tool): lower average time to completion at similar quality and cost.
- Vision: give it a container with the raw images and PIL or OpenCV, or at least a crop tool.

## Effort and thinking (MONITOR)

- Default `high`; `xhigh` for the most capability-sensitive work, `medium` or `low` for routine work.
  Effort is "the primary control for the trade-off between intelligence, latency, and cost". Lower
  settings on Fable 5 "often exceed `xhigh` performance on prior models" [chk-claude-pages].
- Per-message effort is not accepted on Fable 5 (400); on Fable 5.1 it is (beta) and keeps the cache.
- Asking the model to echo its reasoning can trigger `reasoning_extraction` [claude-f3].

## Caching and pricing (VOLATILE)

- $10 / $50 per MTok for both; 5-minute cache write $12.50, 1-hour write $20; cache read $1 on
  Fable 5 and $0.25 on Fable 5.1 (0.025× base input, against 0.1× elsewhere); batch 50% off ($5 /
  $25). Minimum cacheable prompt 512 tokens.
- Anthropic estimates that Fable 5.1's read price lowers typical workloads' price by about 25% and
  highly agentic ones' by up to about 45% [chk-fable-page, defined in
  [practices/long-context-and-compaction.md](../../practices/long-context-and-compaction.md#sources)].
- Fable 5 returns 400 for per-message effort; on Fable 5.1 a per-message effort change and a
  mid-conversation system message keep the cache. The full rules are in
  [practices/prompt-caching.md](../../practices/prompt-caching.md#2-anthropic-volatile).
- Rate limits: one combined Fable limit covers Fable 5.1 and Fable 5; Mythos 5.1 and 5 share a
  separate one.

## Lineage (VOLATILE)

Each row is Anthropic's own claim unless tagged.

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Mythos Preview (gated) | 2026-04-07 | Invitation-only through Project Glasswing; the first Mythos-class model | claude-g6 |
| Fable 5 / Mythos 5 (same model) | 2026-06-09 (suspended 06-12 under a US export-control directive; redeployed 07-01) | New tier above Opus. Thinking adaptive only and cannot be disabled. One brief principle replaces an enumerated list; skills written for older models are "often too prescriptive". Ground progress claims in tool results, give reasons, provide a memory file, show no context countdown. Asking it to echo its reasoning can trigger `reasoning_extraction` refusals. $10/$50, 1M context, 128K output, Opus 4.7's tokenizer; 30-day data retention required, so a request from an organization set for zero data retention returns 400; raw thinking never returned (a summary on request, empty by default). Classifiers aimed at offensive cybersecurity, biology and extraction of its thinking decline with `stop_reason: "refusal"`, with Opus 4.8 as the fallback. Lower effort settings "often exceed `xhigh` performance on prior models". Trained to use bash and crop tools on flipped, blurry or noisy images | claude-g9, claude-f3, chk-claude-pages |
| Fable 5.1 / Mythos 5.1 (Mythos: approved Glasswing participants only) | 2026-09-01 | Fewer progress updates (ask for them); less formatting (drop anti-markdown rules on this model only); denser prose. May stop early unless told it runs autonomously. Adds unrequested fixes and tests unless told to keep extras out. Less search at low effort. Rejects forced `tool_choice`. Append-only history recommended for every integration; the thinking-prefix check applies to accounts created on or after 2026-08-31 and not to Mythos 5.1. Per-turn reminders go in turn-scoped system messages | claude-g12, claude-f20 |

*Fable 5's launch figures.* Its lead over Opus 4.8 was uneven: 80.3% against 69.2% on SWE-Bench Pro
and, on FrontierCode's hardest Diamond split only, 29.3% against 13.4%, in Vellum's summary of the
launch figures [chk-fable-coverage]; the announcement's "10-point jump over Opus" on analytics and
its 25–30% faster spreadsheet runs are customers' quotes about their own benchmarks
[chk-claude-pages].

*Benchmarks that disagree.* xAI's Grok 4.7 announcement lists Fable 5.1 at 57.9% on Terminal-Bench
4.0; Anthropic's Opus 5.5 announcement lists it at 55.8% [chk-xai-47, chk-anthropic-55]. Fable 5.1
scored 66 on Artificial Analysis's index v4.2 and 53 on v4.3, which are not comparable
[open-weight-newer]. On Scale's SWE-Bench Pro V2 Fable 5.1 scored 92.2 [measured-g22]. Details in
[../cross-family.md](../cross-family.md#9-conflicts-and-gaps-in-the-evidence).

## Announced, not released

| Model | Announced | Status | Source |
| --- | --- | --- | --- |
| Claude Fable 5.2 | 2026-09-21 | Rumour only; Anthropic has not commented. Not found in the release check of 2026-10-01 | TestingCatalog [claude-newer], chk-releases |

## Sources

- [chk-fable-coverage] Vellum on Fable 5 and Mythos 5, 2026-06-09
  <https://www.vellum.ai/blog/claude-fable-5-and-mythos-5-benchmarks-explained>, read 2026-10-01.
- [chk-claude-pages] is defined in [claude-5-family-prompting.md](claude-5-family-prompting.md#sources);
  [chk-xai-47] in [../xai/grok.md](../xai/grok.md#sources); [chk-anthropic-55] in
  [opus.md](opus.md#sources); [chk-releases] in [../cross-family.md](../cross-family.md#sources).
- Read 2026-10-01: Fable 5.1 overview, what's new and prompting guide; Fable 5 overview,
  introduction ("Introducing Claude Fable 5 and Claude Mythos 5"), migration guide and prompting
  guide; refusals and fallback; rate limits; release notes (URLs above).
- Anthropic, "Update: Claude Fable 5 and Mythos 5 redeployed", 2026-06-30, read 2026-10-01
  <https://www.anthropic.com/news/redeploying-fable-5>.
- Anthropic, Claude Fable 5 and Mythos 5 announcement, 2026-06-09
  <https://www.anthropic.com/news/claude-fable-5-mythos-5>.
