---
last_checked: 2026-10-01
volatility: MONITOR (stable in direction; re-check at a new Claude generation or a new Anthropic prompting guide)
sources:
  - https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models (2026-07-24)
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
  - https://platform.claude.com/docs/en/about-claude/models/overview
  - https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback
  - https://platform.claude.com/docs/en/release-notes/overview
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
---

# Claude 5 generation: prompting shared across Fable, Opus and Sonnet

What Anthropic says about prompting its Claude 5 models as a group, which practices it retired,
which API behaviours every current Claude 5 model shares, and how its advice moved release by
release. For anyone writing a system prompt, a `CLAUDE.md`, a skill or harness text that a Claude
5 model will read. What holds for one model only is in that model's file:
[fable.md](fable.md), [opus.md](opus.md), [sonnet.md](sonnet.md), [haiku.md](haiku.md); releases
before Fable 5 are in [earlier-generations.md](earlier-generations.md). The direction across
families is in [../cross-family.md](../cross-family.md).

Labels and citations follow [../cross-family.md](../cross-family.md#evidence-labels-and-citations):
a bracketed id resolves in [`../../_evidence/2026-09-25.jsonl`](../../_evidence/2026-09-25.jsonl);
`chk-` ids are defined under Sources in the file named there.

## Current lineup (VOLATILE)

From Anthropic's models overview and model pages, read 2026-10-01 [chk-claude-models]:

| Model | API id | Released | Context / max output | Price per MTok (input / output) | Thinking | Default effort | Knowledge cutoff |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Fable 5.1 | `claude-fable-5-1` | 2026-09-01 | 1M / 128K | $10 / $50 | Adaptive, always on | `high` | Jun 2026 |
| Claude Opus 5.5 | `claude-opus-5-5` | 2026-09-22 | 1M / 128K | $4 / $20 | Adaptive, always on | `medium` | Jun 2026 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | 2026-09-28 | 1M / 128K | $2 / $10 | Adaptive (lowest setting `between_tools`) | `high` | Jun 2026 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 2025-10-15 | 200K / 64K | $1 / $5 | Extended (manual budget) | none | Feb 2025 |

- **Legacy, still available:** Fable 5, Opus 5, Opus 4.8, Opus 4.7 and others; Sonnet 4.5's
  deprecation was announced on 2026-09-30, with retirement on the Claude API on 2026-11-30.
- **Tokenizer.** Every model from Opus 4.7 on uses the tokenizer introduced with it: 1M tokens is
  about 555,000 words or 2.5M Unicode characters, against about 750,000 words before; the same text
  produces roughly 30% more tokens than on earlier models.
- **Batch output.** On the Message Batches API, Opus 5.5, Opus 5, Sonnet 5.5, Sonnet 5, Opus 4.8,
  4.7, 4.6 and Sonnet 4.6 accept up to 300K output tokens with the `output-300k-2026-03-24` beta.
- **Prompt-cache reads** cost 10% of base input, except 2.5% on Fable 5.1 and Mythos 5.1 and 5% on
  Opus 5.5; batch requests are 50% off. The caching mechanics, per-model minimum prefixes and what
  invalidates a cache are in [practices/prompt-caching.md](../../practices/prompt-caching.md#2-anthropic-volatile).
- **Platforms.** Every current model is on the Claude API, Amazon Bedrock, Google Cloud, Microsoft
  Foundry and Claude Platform on AWS. Mythos models (Mythos 5, 5.1) are offered only to approved
  Project Glasswing participants.

## Retired practices (MONITOR)

Anthropic removed more than 80% of Claude Code's system prompt "for models like Claude Opus 5 and
Claude Fable 5 with no measurable loss on our coding evaluations", diagnosing that it had been
"overconstraining Claude Code, both through our system prompt and in our CLAUDE.md files and
skills" (blog, 2026-07-24) [claude-f6, forward-1, forward-2]. Lab measurement. It retired:

1. **Hard never-do rules.** The old system prompt said "In code: default to writing no comments.
   Never write multi-paragraph docstrings…"; the new one says "Write code that reads like the
   surrounding code: match its comment density, naming, and idiom." Constraints "were once needed
   to avoid worst case scenarios", and many can now be deleted "and let the model use surrounding
   context and judgement instead"; skills should avoid being overconstrained "except in highly
   important areas".
2. **Tool-use examples.** "With our newest models, we've found that giving examples actually
   constrains them to a certain exploration space." Invest instead in expressive tools,
   parameters and files (an enumerated `status` field already tells the model how to use it).
   Examples that fix an output format still steer it [claude-f22], and OpenAI's GPT-5.6 guide
   likewise keeps examples "when they encode a product requirement or correct a measured gap"
   ([../openai/gpt-5.6-family.md](../openai/gpt-5.6-family.md#prompting-monitor)): strategy
   demonstrations go, output contracts stay (inference across the two labs).
3. **Verification and review instructions in the system prompt.** Claude Code moved verification
   and code review into skills loaded when needed (progressive disclosure), and defers some tool
   definitions behind a tool search. For Opus 5 Anthropic goes further: delete explicit
   verification and re-check instructions ("double-check your answer", "use a subagent to verify"),
   which cause over-verification on that model ([opus.md](opus.md#behaviour-monitor)). This
   reverses the older advice to ask the model to check itself.
4. **Repeated instructions and end-of-context emphasis.** Earlier models sometimes needed
   repetition or listened better to the end of the context; Claude Code deleted those repeats and
   put tool guidance in the tool descriptions.
5. **`CLAUDE.md` as memory, and simple specs.** Claude Code now saves memories itself; rich
   references (an HTML mockup, a test suite, code in another repository, rubrics) serve better
   than a Markdown description. Keep `CLAUDE.md` light: what the repository is for and its
   gotchas, not what the model can see for itself.

## Standing guidance (MONITOR)

Each line names the page it comes from; where a page names one model, the advice was written for
that model.

- **De-prescribe.** Skills written for earlier models are "often too prescriptive for Claude Fable 5
  and can degrade output quality. Review and consider removing older instructions if default
  performance is better" (Fable 5 guide). State the goal and constraints rather than steps
  [claude-g9].
- **Conciseness has to be asked for.** Effort sets how much the model thinks, not how much it says;
  on Opus 5 "a short conciseness instruction is effective", paired in a long system prompt with a
  short reminder near the end (Opus 5 guide; no reduction is quantified). Claude 4 and later models
  default to a more concise style that needs explicit direction (best practices).
- **Plain conditions, not emphasis.** Where a prompt said "CRITICAL: You MUST use this tool
  when…", use "Use this tool when…"; "If in doubt, use [tool]" causes over-triggering, since models
  from Opus 4.5 on respond more strongly to the system prompt (best practices) [claude-f4,
  claude-f5]. A tool description says when to call the tool.
- **State the scope.** Opus 5 can widen a task; Anthropic's scope block ("Deliver what was asked, at
  the scope intended… Finish the whole task, and stop short of actions that are clearly beyond what
  was asked") gives it the bound (Opus 5 guide). On Fable 5.1 an instruction to leave out
  unrequested extras made "unrequested additions and committed test code drop substantially with no
  measurable change in task success" (Fable 5.1 guide; lab) [claude-f15].
- **No numeric context countdown.** Shown a remaining-token countdown, Fable 5 can suggest a new
  session, offer a handoff or trim its own work; avoid surfacing such counts, or add a reassurance
  that context is ample (Fable 5 guide) [claude-f25]. On Sonnet 5.5 a countdown after every tool
  result can make a user's message read as injected text ([sonnet.md](sonnet.md)). Which models get
  context-awareness tags is in
  [practices/long-context-and-compaction.md](../../practices/long-context-and-compaction.md#3-context-awareness-countdowns-and-early-wrap-up-volatile).
- **Ground progress claims in tool results.** Asking Fable 5 to audit each progress claim against a
  tool result from the session "nearly eliminated fabricated status reports even on tasks designed
  to elicit them" (Fable 5 guide; lab) [anthropic-21, claude-f18].
- **Give the model a memory surface.** Fable 5 "performs particularly well when it can record
  lessons from previous runs and reference them"; say where, and in what shape: one lesson per file
  with a one-line summary, corrections and confirmed approaches with why they mattered, update
  rather than duplicate, delete what turns out wrong (Fable 5 guide; no measurement). The evidence on
  agent memory is in [practices/agent-memory.md](../../practices/agent-memory.md).
- **Give the reason, not only the request.** Context about why lets Fable 5 "connect the task to
  relevant information rather than inferring intent on its own" (Fable 5 guide) [claude-f11].
- **Say when a run is autonomous.** Deep in a long session Fable 5 can end a turn on a statement of
  intent without the tool call, or ask permission it does not need; for autonomous pipelines
  Anthropic adds a reminder that begins "You are operating autonomously. The user is not watching in
  real time…" (Fable 5 guide). Fable 5.1 and Opus 5.5 have their own versions
  ([fable.md](fable.md), [opus.md](opus.md)).
- **Scope correction narration.** Opus 5 narrates corrections to its earlier statements more than
  earlier models; Anthropic's line limits it to corrections "when the error would change the user's
  code, conclusions, or decisions" (Opus 5 guide).
- **Sweep effort down when migrating.** Fable 5's lower settings "often exceed `xhigh` performance on
  prior models"; Opus 5's `low` and `medium` "produce strong quality at a fraction of the tokens and
  latency"; effort level names do not mean the same amount of thinking across models, so re-run the
  sweep on your own evaluations rather than carry a setting over [claude-f1, chk-claude-pages].
- **Filter words in review prompts depress recall.** "Only report high-severity issues", "be
  conservative" or "don't nitpick" are followed literally by Opus 4.8, Sonnet 5 and Opus 5: ask for
  coverage and filter in a separate step, or state a concrete bar [claude-f13, measured-f14].
- **Do not ask for reasoning as response text.** Prompts, skills or harness instructions that tell
  Fable 5, Fable 5.1, Opus 5.5 or Sonnet 5.5 to echo, transcribe or explain its internal reasoning
  can be declined with the `reasoning_extraction` refusal category; read summarized thinking blocks
  instead. Server-side fallback does not retry that category, and since 2026-09-24 one that arrives
  before any output is billed [claude-f3].
- **Context engineering.** Aim for the smallest set of information that fully specifies the
  expected behaviour, which need not be short; test a minimal prompt on the most capable model and
  add instructions and examples for the failures that testing finds; keep sections distinct, though
  their exact formatting likely matters less as models improve [anthropic-2, anthropic-3].

## Shared API behaviour (VOLATILE)

- **Thinking.** Adaptive thinking on every Claude 5 model; `budget_tokens` (manual extended
  thinking) returns 400 on all of them; non-default `temperature`, `top_p` or `top_k` returns 400
  from Opus 4.7 on; prefilling the assistant turn returns 400. Whether thinking can be turned off
  differs by model: never on Fable and Opus 5.5, at `high` or below on Opus 5, only before the
  first reply on Sonnet 5.5 (`between_tools`). `thinking.display` defaults to `"omitted"` (empty
  thinking text); `"summarized"` returns a summary; the raw chain of thought is never returned.
- **Forced tool use removed.** `tool_choice` `any` or `tool` returns 400 on Fable 5.1, Mythos 5.1,
  Opus 5.5 and Sonnet 5.5; use `auto` with strict tool use or structured outputs, and say in the
  prompt when the tool applies [claude-g12, claude-g13, chk-sonnet-55].
- **Thinking blocks are bound to model and conversation.** A block records the model that wrote
  it; a model reads only some others' blocks, and the API silently drops one the target model
  cannot read. For accounts created on or after 2026-08-31, Fable 5.1, Opus 5.5 and Sonnet 5.5
  reject (400) a replayed block whose prefix (system prompt, tools, an earlier message) changed;
  Mythos 5.1 does not run the check. Treat history as append-only: change instructions with a
  mid-conversation system message, per-turn reminders with turn-scoped system messages
  (`clear_at: "next_user_message"`, beta), tools with mid-conversation tool changes, and trim with
  server-side compaction or context editing [claude-g12].
- **Text between tool calls** arrives as progress-update `thinking` blocks on Fable 5.1, Opus 5.5
  and Sonnet 5.5, empty under the default display; `display: "updates"` (beta) returns them as
  text.
- **Per-message effort** (beta, `mid-conversation-output-config-2026-07-01`) changes effort for
  later turns without invalidating the cache on Fable 5.1, Mythos 5.1, Opus 5, Opus 5.5 and Sonnet
  5.5; a top-level effort change invalidates it.
- **Safeguard refusals.** Fable 5.1, Fable 5, Opus 5.5, Opus 5 and Sonnet 5.5 run safety
  classifiers. A decline is HTTP 200 with `stop_reason: "refusal"` and `stop_details.category` one
  of `cyber`, `bio`, `frontier_llm`, `reasoning_extraction`, `general_harms` (or null); branch on
  the stop reason, not on `content`. Since 2026-09-24 a decline before any output is billed in the
  `bio`, `frontier_llm` and `reasoning_extraction` categories, on every platform; a mid-stream
  decline bills input and the output already streamed. Server-side fallback (`fallbacks:
  "default"`, beta, `server-side-fallback-2026-07-01`; the default mode added 2026-07-24) retries
  on the model Anthropic recommends for the category, chosen server-side; it is not supported on
  Message Batches and not available on Bedrock, Google Cloud or Microsoft Foundry, where the SDK's
  client-side fallback serves. `fallbacks` does not reach model calls made inside tool execution.
  A retry on another model writes that model's cache from scratch; fallback credit refunds that
  cost.

## Direction across releases (STABLE)

Anthropic's advice moved from compensating for the model (extra reach, emphasis, prefill, manual
chain of thought, `budget_tokens`) to stating the outcome: brief principles, stated intent, a
finish line, stop conditions, and progress claims checked against tool results [claude-trend].
The API removed five controls across the ten releases since February 2026: prefill (Opus 4.6),
`budget_tokens` (Opus 4.7), non-default sampling (Sonnet 5), disabling thinking (Fable 5) and
forced `tool_choice` (Fable 5.1, Opus 5.5, Sonnet 5.5); Mythos Preview, Opus 4.8 and Opus 5
removed none [claude-g5, claude-g7, claude-g10, claude-g9, claude-g12, claude-g13, chk-sonnet-55].
Literalism rose (Opus 4.7, 4.8, Sonnet 5), while Opus 5 expanded scope and Fable 5.1 added
unrequested fixes. Narration, delegation and verification each flipped between releases
[claude-f19, claude-f21]:
- narration: forced-update scaffolding removed, then Opus 5 over-narrated, then Fable 5.1 narrated
  too little, then Opus 5.5 moved updates into thinking blocks;
- delegation: eager (Opus 4.6), fewer subagents (Opus 4.8), eager again (Opus 5, Fable 5).

On the pattern of 2026, a new frontier release is likely every 3 to 7 weeks, each with its own
prompting page and some "remove this old instruction" advice, which favours shipped text that
states outcomes, scope, stop conditions and evidence standards over model-specific behavioural
patches [claude-next]. Within one week Anthropic told Opus 5.5 users to delete "think carefully"
lines and gave Sonnet 5.5 users "Think the problem through before you answer." for reasoning
tasks answered in JSON [forward-16, chk-sonnet-55]: guidance is per model, even within a family.

## Sources

- [chk-claude-models] Anthropic models overview, read 2026-10-01.
  <https://platform.claude.com/docs/en/about-claude/models/overview>
- [chk-claude-pages] Anthropic pages read 2026-10-01: prompting Claude Opus 5
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5>;
  prompting Claude Fable 5
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5>;
  the Fable 5 and Opus 5 model, what's-new and migration pages under
  `https://platform.claude.com/docs/en/models/{fable-5,opus-5}/`; effort
  <https://platform.claude.com/docs/en/build-with-claude/effort>; rate limits and fast mode;
  refusals and fallback <https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback>;
  the Fable 5 announcement, 2026-06-09 <https://www.anthropic.com/news/claude-fable-5-mythos-5>.
- Anthropic, the new rules of context engineering for Claude 5-generation models, 2026-07-24, read
  2026-10-01 <https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models>
  (also <https://claude.dev/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models/>).
- Prompting best practices (living), read 2026-10-01
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>.
- Claude Platform release notes, read 2026-10-01 <https://platform.claude.com/docs/en/release-notes/overview>.
- Effective context engineering for AI agents, 2025-09-29, read 2026-10-01
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>.
