---
last_checked: 2026-10-01
volatility: MONITOR (defaults, removed controls and prices changed at each Opus release in 2026)
sources:
  - https://platform.claude.com/docs/en/models/opus-5-5/overview
  - https://platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
  - https://platform.claude.com/docs/en/models/opus-5/overview
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
  - https://platform.claude.com/docs/en/build-with-claude/fast-mode
  - https://platform.claude.com/docs/en/api/rate-limits
  - https://www.anthropic.com/news/claude-opus-5-5
  - https://claude.dev/blog/getting-the-most-out-of-opus-5-5/
---

# Claude Opus 5 and 5.5

What Anthropic's current Opus models are, what their API accepts, how they behave, how Anthropic
says to prompt them, what they cost, and how they differ from each other. For anyone running Opus
in an agent or writing text it will read. Shared Claude 5 behaviour is in
[claude-5-family-prompting.md](claude-5-family-prompting.md); Opus 4.x is in
[earlier-generations.md](earlier-generations.md). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and availability (VOLATILE)

| | Opus 5.5 | Opus 5 |
| --- | --- | --- |
| API id | `claude-opus-5-5` | `claude-opus-5` |
| Status | Latest; released 2026-09-22; retirement not sooner than 2027-09-22 | Legacy; released 2026-07-24; retirement not sooner than 2027-07-24 |
| Built for | Long-running agentic coding and knowledge work | Complex agentic coding and enterprise work; "a step-change improvement over Claude Opus 4.8" |
| Context / output | 1M (default and maximum) / 128K; 300K on Message Batches (beta) | Same |
| Price per MTok | $4 / $20 (cut 20%) | $5 / $25 (Opus 4.8's price) |
| Thinking | Adaptive, always on | Adaptive, on by default; can be disabled at effort `high` or below |
| Default effort | `medium` | `high` |
| Knowledge cutoff | Jun 2026 | May 2026 |
| Comparative latency | Moderate | — |

- Both on the Claude API, Bedrock (`anthropic.claude-opus-5-5`), Google Cloud, Microsoft Foundry and
  Claude Platform on AWS.
- **Rate limits.** Opus 5.5 and Opus 5 each have their own limit, outside the combined Opus 4.x
  bucket (Opus 4.8, 4.7, 4.6, 4.5); fast mode has dedicated limits.
- **Speed.** Opus 5.5 "generates output tokens more than 30 percent faster than Claude Opus 5 and
  tends to finish the same task with fewer tokens" (Opus 5.5 guide).
- Opus 5.5 is "the first Opus model to launch with Fable-level bio and cyber safeguards"; in Claude
  apps and Claude Code most flagged messages move to an older model (Opus 5.5 blog).

## API surface (STABLE)

- **Thinking.** Opus 5: omitting `thinking` runs adaptive thinking; `{"type": "disabled"}` is
  accepted only at `high` or below, and with `xhigh` or `max` returns 400, validated per request.
  Opus 5.5: thinking cannot be disabled; `disabled` or `{"type": "enabled", "budget_tokens": N}`
  returns 400 `invalid_request_error`; omit `thinking` or send `{"type": "adaptive"}`. Every
  response can begin with `thinking` blocks (empty at the default display), so read blocks by
  `type`.
- **Rejected on both:** `budget_tokens`, non-default `temperature`/`top_p`/`top_k`, prefill. Opus
  5.5 also rejects forced `tool_choice` (`any`, `tool`): use `auto` with strict tool use, and say in
  the prompt when the tool applies.
- **Thinking blocks (5.5).** Opus 5.5 reads blocks from Opus 5, earlier Opus, Sonnet and Haiku, and
  on the Claude API from Sonnet 5.5, but not from Fable or Mythos models; on the Claude API Fable 5.1
  and Mythos 5.1 read Opus 5.5's blocks, and no other model does. The prefix check (400 on a replayed
  block after an edit) is enforced for accounts created on or after 2026-08-31, on the Claude API and
  cloud platforms.
- **Text between tool calls (5.5)** arrives in progress-update `thinking` blocks, empty at the
  default `display: "omitted"`; an application that streamed that text goes quiet until it sets
  `display: "updates"` (beta) or `"summarized"`.
- **Computer use (5.5).** On the Claude API and Google Cloud only the `computer_toolset_20260801`
  toolset; the earlier `computer_20251124` tool returns 400 (it keeps working on Bedrock).
- **Supported:** structured outputs (`output_config.format`), per-message effort (beta), mid-
  conversation system messages, task budgets, batch, Files API, PDFs, vision, server and client
  tools, tools defined inside a mid-conversation system message (`inline-tools-2026-09-15`, beta),
  compaction on demand (`compact-2026-09-04`, beta).
- **Safeguards.** Opus 5 can return `stop_reason: "refusal"`; Opus 5.5 adds a biology classifier to
  the cybersecurity one, the same biology safeguards as Fable 5.1, and the `reasoning_extraction`
  category. Finding vulnerabilities in source code is allowed; high-risk dual-use security activity
  is not. Server-side fallback (`fallbacks: "default"`, Claude API only, beta) picks the retry model
  per refusal category server-side (the refusals page's example selects Opus 4.8); it does not
  retry `reasoning_extraction`, and is not available through Bedrock, Google Cloud or Foundry. A
  pre-output refusal counts against rate limits either way. Life-sciences organizations can apply to
  the Life Sciences Verification Program.

## Behaviour (MONITOR)

Opus 5, compared with Opus 4.8 (its guide; it "performs well out of the box on existing Claude Opus
4.8 prompts"):
- **Longer output.** User-facing replies run longer, agentic messages are often longer, and files it
  writes (reports, Markdown, summaries) are often longer. Effort controls thinking, not visible
  length, so lowering it does not reliably shorten a reply [chk-claude-pages].
- **Narrates readily**, announcing what it is about to do; positive examples of the wanted style
  work better than prohibitions.
- **Verifies its own work unprompted**: explicit verification instructions, and harness steps that
  add separate verification, cause over-verification; removing them "reduces wasted tokens with no
  loss in quality" (lab claim) [claude-g11, anthropic-22].
- **Expands scope**, adding steps or applying its own view of what the task should be [claude-g11].
- **Delegates to subagents more readily than prior models**, a reversal from Opus 4.8; delegation
  multiplies cost on small tasks [claude-f21].
- **Catches its own mistakes** and narrates corrections more than earlier models.
- **Review filters taken literally**: "only report high-severity issues" or "be conservative" makes
  it report less; ask for everything and filter in a separate pass. Its review keeps precision and
  recall at lower effort.
- **With thinking disabled** (only possible at `high` or below), two artifacts: tool calls written
  into visible text instead of a `tool_use` block (the turn completes, the call never runs, and the
  leaked text stays in the history; most common on tool-heavy work such as search), and `<thinking>`
  or other internal tags in the reply, made worse by a rule telling it not to think.
- **Vision** is strongest with tools to analyze, crop and verify; tool use is "a more cost-effective
  lever than thinking alone".
- Instruction following, tool calling and reasoning "stay consistent throughout the window".

Opus 5.5, compared with Opus 5 (its what's-new page and guide; "Existing Claude Opus 5 prompts should
perform well without changes"):
- **Default effort `medium`**, and more thinking per turn at a given level, most at `xhigh` and
  `max`: a carried-over setting means longer turns and more output tokens [claude-g13].
- In Anthropic's testing, at `medium` it matched or beat Opus 5 at `high` on multistep work in a real
  repository, in fewer steps and tokens; it sustains multi-hour autonomous work better; early testers
  reported stronger code review [lab].
- Much less likely to state a wrong figure or cite the wrong source; catches easy-to-miss details.
- Reads dense charts, diagrams and screenshots far more precisely without tools: at its lowest effort
  it read chart values more accurately than Opus 5 at its highest, using a small fraction of the
  output tokens; at default effort it matched Opus 5's computer-use success at a much higher effort
  [lab].
- On long multi-part tasks some progress updates end the turn with text (`end_turn`), which an
  unattended loop can mistake for completion.
- Resists indirect prompt injection better than any earlier Opus model.
- In multi-turn chat it sometimes revisits earlier answers while thinking about a new message.
- Asked for frontend work without direction, it falls back on a few default styles; a general "avoid
  a generic AI look" swaps one default for another.

Independent and vendor measurements:
- METR judged Opus 5.5 an incremental, on-trend step over Fable 5.1, not a discontinuous jump, with
  remaining weaknesses in judgement and foresight, and published no time horizon for it (Anthropic
  reviewed the summary) [claude-trend, measured-g24].
- Opus 5.5 scores 66.4% on Terminal-Bench 4.0 by Anthropic's figure, against 59.6% in Artificial
  Analysis's mini-swe-agent run [indep; measured-g23]. On Scale's SWE-Bench Pro V2 Opus 5 (Claude
  Code, xhigh) scored 98.0, the top of that table [measured-g22].
- Scale caught Opus 5 forging a Go checksum [measured-g22].
- On one vendor's code-review benchmark for Opus 5.5, the lower-effort setup caught 51 issues
  against Max's 50 with higher precision on 80 patterns, while Max caught 10 against 8 on 13 harder
  cases (a tie at 10 counting findings outside the changed lines); on FrontierCode higher effort
  produced scope creep (relayed) [claude-f23].
- Zvi Mowshowitz's summary of the Opus 5.5 system card (2026-09-23) reports that internal use found
  overstated scope and stripped qualifiers rising for Opus 5.5, a finding later disputed (from the
  detail of [measured-f21]; the summary itself was not fact-checked).

## Prompting (MONITOR)

Opus 5 (its guide):
- **Length.** A short conciseness instruction is effective ("Keep responses focused, brief, and
  concise…"); in a long system prompt add a short reminder near the end ("Keep outputs reasonably
  concise."). For written files: "Match the length of written documents to what the task needs:
  cover the substance, but do not pad with filler sections, redundant summaries, or boilerplate."
  No measured reduction is given. This holds for Opus 5; for GPT-6 Sol and Luna, whose deliverables
  were measured omitting required elements, the remedy is to name what a deliverable must keep
  ([../openai/gpt-6-family.md](../openai/gpt-6-family.md)).
- **Narration cadence.** Describe it: one sentence before the first tool call, an update only on an
  important finding or change of direction, the outcome first at the end.
- **Remove verification instructions** ("include a final verification step for any non-trivial
  task", "use a subagent to verify") and re-check prompts ("double-check your answer"). The Fable 5
  guide's fresh-context verifier advice conflicts; each holds for its own model.
- **Scope block** for narrow tasks: "Deliver what was asked, at the scope intended…".
- **Subagents.** Say which scenarios warrant delegation ("only for large tasks that are genuinely
  independent and parallelizable… do not use subagents to verify or double-check your own work"),
  or cap them: in Claude Code and the Agent SDK, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`,
  `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` and the SDK's `max_budget_usd`, which need Claude Code
  2.1.217 or later. Claude Code adds its own delegation instruction for Opus 5 only with its
  `claude_code` system-prompt preset.
- **Correction narration:** limit it to errors "that would change the user's code, conclusions, or
  decisions".
- **Thinking disabled:** keep thinking on and lower effort instead ("thinking enabled at `low`
  effort performs better than thinking disabled at similar cost"); where it must stay off, one
  general instruction (permission to speak before a tool call, say so when no tool fits, no internal
  tags), without naming thinking tags.

Opus 5.5 (its guide and the "Getting the most out of Opus 5.5" post):
- **Delete "think carefully" lines.** The model already thinks before every reply; in Anthropic's
  testing in a chat product, removing such a line made replies start sooner with no clear drop in
  quality [claude-f2, forward-16]. To keep earlier answers settled in multi-turn chat, two
  sentences at the end of the system prompt reduce thinking on follow-ups; leave them out where
  re-examination matters.
- **Migrating from thinking disabled:** start at `low` and measure; "Answer directly without
  deliberating." can reduce thinking further; remove instructions that had the model write its
  reasoning in the reply (now a `reasoning_extraction` risk); re-test the thinking-disabled
  mitigations; read responses by block type.
- **Unattended runs.** Treat a text-only end of turn as a report, not proof of completion; keep the
  task's parts in a checklist; when a turn ends with items open and no blocker, send a short user
  message naming them, or have a smaller model check a stated completion condition; stop after two
  or three automatic continuations; wait for running background work. A system-prompt addition that
  names the early stops to avoid (and the stops wanted) makes them rarer; add it from the first
  request, since adding it later edits the system prompt and invalidates earlier thinking blocks.
  Keep your own confirmation step for risky or irreversible actions [claude-g13].
- **Stopping rule in `CLAUDE.md`.** On long tasks Opus 5.5 sometimes stops to report; Anthropic's
  guidance puts a short rule in `CLAUDE.md` on when to stop and ask, its example stopping "only when
  you can't continue without me, or before anything destructive: deleting data, force-pushing, or
  changing anything outside this repository" [agent-files-20].
- **Progress updates:** receive them (`display: "updates"`), give a send-to-user tool declared from
  the first request, ask for the cadence wanted, and have the harness append a turn-scoped reminder
  after several silent tool steps (five, for example), stopping after two or three; in Anthropic's
  testing this "roughly halved the share of tasks with a long silent stretch, with no measurable
  change in cost" [lab].
- **Multi-app workflows:** one sentence telling it to look through the relevant sources before acting
  completed noticeably more tasks correctly at `medium` and `max`, at slightly more tool calls; keep
  untrusted content out of what it searches [lab].
- **Time signals for multiagent work:** append elapsed time against a budget (`elapsed 340s /
  1200s`) to each message; teams finished sooner with comparable quality; the budget is advisory
  [lab].
- **Mark pasted text:** wrap pasted blocks in opening and closing tags carrying a short random id
  and add a system-prompt note; it can make the model slightly more cautious, and tags can be
  imitated [claude-g13].
- **Visual inputs:** re-test old vision scaffolding; for the densest inputs, higher resolution and a
  container with PIL or OpenCV (or a crop tool) still add accuracy, more so at higher effort.
- **Frontend:** name the specific patterns to avoid, and extend the list after checking what it
  used instead [claude-f10].

## Effort and thinking (MONITOR)

- Opus 5: default `high`; full ladder `low`, `medium`, `high`, `xhigh`, `max` (`max` for
  capability-critical work); "use `low` and `medium` liberally as your primary control for token
  cost and response time wherever quality holds, and step up to `xhigh` for demanding coding and
  agentic work"; re-run the sweep if defaults were carried over [chk-claude-pages].
- Opus 5.5: start at `medium`, set it explicitly, test several levels; level names do not mean the
  same thinking across models; Opus 5.5 at `medium` matches or exceeds Opus 5 at `high` on coding
  and knowledge-work evaluations, and on several coding evaluations `low` "comes close to it at much
  lower cost". Set `max_tokens` with room for thinking (128,000 worked well for long agentic coding in
  Anthropic's testing); reserve `xhigh` and `max` for work with a measured gain; to get less
  thinking, lower effort before adding prompt instructions [claude-g13, claude-f23]. Anthropic's
  Opus 4.8 page had recommended `xhigh` for most coding [claude-f23].
- A top-level effort change invalidates the prompt cache; per-message effort (beta) keeps it, on
  both models.

## Caching and pricing (VOLATILE)

| | Input | Output | 5-min cache write | 1-hour cache write | Cache read | Batch |
| --- | --- | --- | --- | --- | --- | --- |
| Opus 5.5 | $4 | $20 | $5 | $8 | $0.20 (0.05×) | $2 / $10 |
| Opus 5 | $5 | $25 | $6.25 | $10 | $0.50 (0.1×) | 50% off |

- Minimum cacheable prompt 512 tokens on both (Opus 4.8: 1,024). Mid-conversation system messages
  keep the cache on both; per-message effort keeps it. The full mechanics are in
  [practices/prompt-caching.md](../../practices/prompt-caching.md#2-anthropic-volatile).
- **Fast mode** (research preview, `speed: "fast"`, `fast-mode-2026-02-01` beta): up to 2.5× output
  tokens per second on Opus 5.5, Opus 5 and Opus 4.8, at $8 / $40 (Opus 5.5) and $10 / $50 (Opus 5,
  Opus 4.8) per MTok; Claude API (including Managed Agents) only, not Bedrock, Claude Platform on
  AWS, Google Cloud or Foundry; not with batch or Priority Tier; dedicated rate limits. Switching
  fast mode invalidates system and message caches. Fast mode was removed from Opus 4.7 (error) and
  Opus 4.6 (runs at standard speed).

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Opus 5 | 2026-07-24 | Verifies its own work unasked, so carried-over verification instructions cause over-verification. Longer output that lower effort does not shorten: replies, agentic messages and written files all run longer, and a short conciseness instruction works, repeated near the end of a long system prompt. Expands scope and delegates readily, so cap subagents (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, Claude Code 2.1.217+). Default effort high; `low` and `medium` give "strong quality at a fraction of the tokens". Thinking disabled only at `high` or below, and then tool calls occasionally leak into the text and never run. $5/$25 (fast mode $10/$50, a research preview on the Claude API only), 1M context as default and maximum, a rate limit apart from the Opus 4.x pool. Vision is strongest with tools to crop and check its work. Anthropic removed more than 80% of Claude Code's system prompt for this generation | claude-g11, claude-f6, chk-claude-pages |
| Opus 5.5 (first of the 5.5 family) | 2026-09-22 | Default effort medium (Opus 5: high); Anthropic says medium matches or beats Opus 5 at high on its coding and knowledge-work evals. Thinking cannot be disabled; forced `tool_choice` removed; progress notes arrive as thinking blocks. Advice: delete "think carefully"; hand over the whole task with a finish line and stop conditions; name the early-stop patterns to avoid; tag pasted text so it is not obeyed; name specific design defaults to avoid. Prices cut 20%, to $4/$20 per 1M tokens | claude-g13, claude-f2, chk-anthropic-55 |

*Benchmarks that disagree.* Anthropic's Opus 5.5 announcement lists Fable 5.1 at 55.8% and GPT-6
Astra at 57.9% on Terminal-Bench 4.0; its Sonnet 5.5 announcement a week later gives Sonnet 5.5
70.6%, above the 66.4% it gave Opus 5.5 [chk-anthropic-55, chk-sonnet-55]. See
[../cross-family.md](../cross-family.md#9-conflicts-and-gaps-in-the-evidence).

## Announced, not released

Anthropic announced expanded Cyber Verification Program access for Opus 5.5 "in the coming weeks"
and Enterprise Frontier Safeguards "beginning later this fall" [claude-next].

## Sources

- [chk-anthropic-55] Anthropic, Claude Opus 5.5 announcement (Terminal-Bench 4.0, Sonnet and Haiku
  5.5, pricing), 2026-09-22 <https://www.anthropic.com/news/claude-opus-5-5>; with "Getting the most
  out of Opus 5.5", 2026-09-22 <https://claude.dev/blog/getting-the-most-out-of-opus-5-5/>, read
  2026-10-01.
- [chk-claude-pages] is defined in [claude-5-family-prompting.md](claude-5-family-prompting.md#sources);
  [chk-sonnet-55] in [sonnet.md](sonnet.md#sources).
- Read 2026-10-01: Opus 5.5 overview, what's new, prompting guide and migration guide; Opus 5
  overview and prompting guide; fast mode; rate limits; refusals and fallback; release notes (URLs
  above).
- Optimizing for cost and intelligence (undated; measurements to 2026-09-20)
  <https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence>.
- CodeRabbit on Opus 5.5 (vendor), 2026-09-22 <https://www.coderabbit.ai/blog/opus-5-5-model-review>;
  METR on Claude Opus 5.5 (Anthropic reviewed), 2026-09-22
  <https://metr.org/blog/2026-09-22-claude-opus-5-5/>; Artificial Analysis on Claude Opus 5.5,
  2026-09-22 <https://artificialanalysis.ai/articles/claude-opus-5-5>.
