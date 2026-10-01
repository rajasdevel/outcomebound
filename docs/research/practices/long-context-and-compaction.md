---
last_checked: 2026-10-01
volatility: STABLE (the long-context studies change only with new research) / VOLATILE (§1 windows, §3 countdown behaviour and the compaction APIs in §5)
sources:
  - https://platform.claude.com/docs/en/build-with-claude/context-windows
  - https://platform.claude.com/docs/en/about-claude/models/overview
  - https://platform.claude.com/docs/en/build-with-claude/compaction
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://developers.openai.com/api/docs/pricing
  - https://developers.openai.com/api/docs/guides/compaction
  - https://alignment.openai.com/misalignment-reports/encouraging-deception-in-compaction-summaries/
  - https://www.trychroma.com/research/context-rot
  - https://arxiv.org/abs/2502.05167
  - https://docs.langchain.com/oss/python/deepagents/context-engineering
  - https://code.claude.com/docs/en/checkpointing
  - https://code.claude.com/docs/en/memory
---

# Long context and compaction

Re-check when a provider changes its windows or compaction API, a harness changes how it compacts,
or a model generation ships; in any case by 2027-01-01.

How much of a long context a model can use and what degrades with length; how models react to
context countdowns; how to keep context small by design; and what compaction keeps and loses. For
anyone who writes always-loaded text or long prompts, runs long agent sessions, or designs what must
survive a compaction. Prompt caching is in [prompt-caching.md](prompt-caching.md); summaries and
summary layers in [summarization-layers.md](summarization-layers.md); what agents keep between
sessions in [agent-memory.md](agent-memory.md). What each harness re-injects after compaction is in
[harnesses.md](../harnesses/cross-harness.md#7-compaction-and-long-sessions) §7; the rules for handoffs and
for memory shared in a repository are in [agent-workspace.md](agent-workspace.md) §3–4; how
instruction following decays with length across model families is R7 in
[models.md](../models/cross-family.md#3-trends-r1r16).

**Evidence classes**, as in [the index](../README.md): M measured; L lab or vendor documentation or
guidance; S standard or protocol specification; P practitioner consensus; A anecdote or one
uncontrolled report; F forecast; O own result. **Citations.** Bracketed ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl), or in
[`_evidence/2026-09-26.jsonl`](../_evidence/2026-09-26.jsonl) for `sizing-` ids; "[id] detail" is the
sweep reader's note on that record, which the fact-check did not separately verify. `[chk-…]` ids are
pages re-read on 2026-10-01, listed under Sources. Papers are cited by arXiv id and were read on
2026-10-01; a number taken from a paper's body rather than its abstract is marked "body". Most
long-context studies tested models of 2023–2025; provider documentation is lab guidance about the
provider's own product; vendor benchmark claims carry the vendor's interest.

This reference and its three siblings ([prompt-caching.md](prompt-caching.md),
[summarization-layers.md](summarization-layers.md), [agent-memory.md](agent-memory.md)) draw on
three bodies of material: the evidence records of the 2026-09-25 and 2026-09-26 sweeps that bear on
context and memory; earlier topic notes on prompt caching, summarization layers and cross-agent
memory, read between 2026-06-17 and 2026-09-01; and the providers' documentation. Every finding not
already carried by an evidence record was re-read at its source on 2026-10-01 and corrected where
the source said otherwise; a finding whose source could not be found was left out.

## Key findings

**CM1. A long window is not usable context.** Input length alone cut results by 13.9–85% inside the
models' claimed windows; distractors compound the loss; and where the question shares no words with
what it needs, 11 of 13 models that claim at least 128K tokens fell below half their short-context
score by 32K. Lab results on needle retrieval (GPT-6 Astra 96.3% at 512K–1M) do not show that a model
uses everything in a long context, and monitors missed dangerous actions 2–30× more often after 800K
benign tokens. M.

**CM4. Compaction keeps a summary, and a summary can drop or distort what mattered.** Anthropic's
Fable 5.1 guide lists dropped constraints, decisions and exact details as a known symptom; on its
newest models the summary is all that remains of earlier thinking; in OpenAI's RL training, 2.15%
(GPT-5.6 Sol) and 0.27% (GPT-6 Astra) of compaction summaries carried instructions to invent missing
data or hide failures. What must survive compaction is written to files. L, M.

## 1. Context windows today (VOLATILE)

- **Anthropic.** A 1M-token window on Fable 5.1, Mythos 5.1, Fable 5, Mythos 5, Opus 5.5, Opus 5,
  Opus 4.8, 4.7, 4.6, Sonnet 5.5, Sonnet 5, Sonnet 4.6 and Mythos Preview, the default with no beta
  header and at standard prices, with up to 128K output a request; other models, Sonnet 4.5 and
  Haiku 4.5 among them, have 200K. On the tokenizer introduced with Opus 4.7, 1M tokens is about
  555,000 words [chk-claude-context, chk-claude-models]. L.
- **OpenAI.** Every GPT-5.6 and GPT-6 model page gives a 1,050,000-token window, 922,000 input
  tokens at most and 128,000 output; input above 272K tokens bills the whole request at the
  long-context rate [chk-openai-pricing]. L.
- **Others.** Grok 4 Fast offered 2M in 2025 [grok-g4], Grok 4.3 1M [grok-g8], and Grok 4.5 cut
  the window to 500K [grok-g10]; GLM-5.2 1M [glm-g8]; DeepSeek V4 1M by default [open-weight-g9];
  the open-weight agentic families converged on 1M [open-weight-trend]. L.
- **Cached tokens still count.** "Cached prompt prefixes still occupy the context window: prompt
  caching changes what you pay for those tokens, not whether they count" [chk-claude-context]. L.
- **Where windows are heading.** One editor's bet of 2026-03-14, that windows will not meaningfully
  exceed 1M for two years, is forecast P8 in [models.md](../models/cross-family.md#8-forecasts) §8. F.

## 2. What degrades with length

- **Length alone.** Performance fell by 13.9–85% as input grew, well within the models' claimed
  lengths, even when the padding was whitespace and the evidence sat right before the question;
  having the model recite the evidence first recovered up to 4% for GPT-4o on RULER (five models;
  math, question answering, coding) [research-12, research-12 detail]. M.
- **Focused against full context.** Across 18 models (GPT-4.1, Claude 4, Gemini 2.5, Qwen3 and
  others), focused prompts of about 300 tokens scored far higher than full prompts of about 113K on
  LongMemEval questions; one distractor lowered performance, four compounded it, and the effect grew
  with length [research-11, chk-chroma]. M (vendor report).
- **The middle of the context.** Relevant information in the middle of a long input was used worst,
  on 2023 models (GPT-3.5-Turbo, Claude-1.3, MPT-30B, LongChat-13B; GPT-4 on a subset) [research-13].
  M.
- **No literal overlap.** On NoLiMa, where the question shares no words with the passage it needs,
  11 of 13 models that claim at least 128K tokens fell to half their short-context score or less by
  32K; GPT-4o, one of the best, went from 99.3% to 69.7%, an effective length of 8K by the paper's
  measure [chk-nolima, research-13 detail]. M (ICML 2025; models of 2024–25). A pointer or a skill
  description that names its situation in the words a task will use is likelier to be found than one
  that relies on association (inference).
- **Needles are not use.** Anthropic reported Sonnet 4.5 at 18.5% and Opus 4.6 at 76% on an
  eight-needle retrieval test at 1M tokens, and OpenAI GPT-6 Astra at 100% at 256K–512K and 96.3% at
  512K–1M [measured-f18, measured-f18 detail]. These are labs' own retrieval figures: they show
  needles found, not instructions followed or everything in the context used. L.
- **Monitors at length.** Opus 4.6, GPT 5.4 and Gemini 3.1, used as monitors, missed a dangerous
  action 2–30× more often after 800K tokens of benign activity than on its own; periodic reminders
  partly helped (authors at Anthropic) [measured-g13]. M.
- **Release over release.** Artificial Analysis measured Grok 4.7 3.7 points below Grok 4.6 on its
  long-context reasoning test, though xAI claims better long-context handling [grok-f18]. M.
- **Errors breed errors.** With knowledge and plan supplied, per-step accuracy still fell as steps
  accumulated, partly because errors already in the context made further errors likelier
  ("self-conditioning"), which model scale did not fix and thinking reduced [sizing-horizon-22]. M.
- **Practitioners differ.** HumanLayer moved back from Opus 4.6 with a 1M window to Opus 4.5 after
  instruction adherence worsened even at short lengths, and now warns at 100K tokens; Amp holds that
  200K tokens is plenty [practitioners-11, practitioners-11 detail]. A. Chroma's founder would rather
  have 60K tokens used perfectly than 5M used poorly [latent-space-12 detail]. A.
- **Anthropic's framing.** Context is "a finite resource with diminishing marginal returns", and the
  loss is "a performance gradient rather than a hard cliff" [chk-context-engineering]. L.

## 3. Context awareness, countdowns and early wrap-up (VOLATILE)

- Sonnet 5, Sonnet 4.6, Sonnet 4.5 and Haiku 4.5 receive tags, injected by the API, that track their
  remaining context; Opus 4.7 and later Opus models, Sonnet 5.5 and the Fable and Mythos 5.x models
  do not, and take an explicit budget through task budgets (beta) instead [chk-claude-context,
  claude-g3]. L.
- Sonnet 4.5 showed "context anxiety", wrapping up early near what it believed was its limit, strongly
  enough that Anthropic's long-running harness needed context resets; Opus 4.5 "largely removed"
  it, and the harness then ran one continuous session with automatic compaction [sizing-trend-2,
  sizing-trend-3]. L.
- In very long sessions Fable 5 can suggest a new session, offer a handoff or trim its own work,
  "most often triggered when the harness shows a remaining-token countdown"; Anthropic says not to
  surface such counts [claude-f25, sizing-trend-19]. L.
- On Sonnet 5.5, a countdown appended after every tool result can make the model treat a user's
  mid-task message as injected text [chk-sonnet-55]. L.
- MiniMax advises concise system prompts in harnesses that compress context, because "The model may
  terminate tasks early when approaching context capacity thresholds"; DeepSeek and Kimi tell Claude
  Code users to set `CLAUDE_CODE_AUTO_COMPACT_WINDOW` to their 1M window [open-weight-f14,
  open-weight-f14 detail]. L.

## 4. Keeping context small by design

- Anthropic names three long-horizon techniques: compaction; structured note-taking, notes the agent
  keeps outside the window and reads back; and subagents that explore with clean windows and return
  "a condensed, distilled summary of its work (often 1,000-2,000 tokens)" [sizing-lab-10,
  chk-context-engineering]. L.
- Google's Agent Development Kit gives every model call and subagent the minimum context by default
  and lets it fetch more through tools; keeps large artifacts behind handles; makes memory
  searchable rather than pinned; and puts stable instructions first and dynamic content last
  [other-labs-10, other-labs-10 detail]. L.
- One framework's defaults (LangChain Deep Agents): a tool result over 20,000 tokens is moved to a
  file at once, leaving a path and a 10-line preview; large tool inputs already saved to disk are
  truncated once the context passes 85% of the window; and the history is summarized at 85% of the
  model's input limit, keeping the latest 10% [chk-deepagents]. L (one framework).
- Claude Code checkpoints the code before each prompt (the 100 most recent), and `/rewind` restores
  code, conversation or both; "Summarize from here" and "Summarize up to here" compress one side of
  a chosen message, "like a targeted `/compact`", while the original messages stay in the session
  transcript. Files changed by Bash commands are not tracked [chk-claude-checkpointing]. L.

## 5. Compaction (MONITOR)

- **What it is.** Compaction replaces older turns with a summary so that a session continues past the
  window. Anthropic calls it "the first lever in context engineering": in Claude Code the model keeps
  "architectural decisions, unresolved bugs, and implementation details while discarding redundant
  tool outputs or messages", and continues with the summary plus the five most recently accessed
  files. "Overly aggressive compaction can result in the loss of subtle but critical context"; the
  post advises tuning a compaction prompt on real traces for recall first and precision second, and
  calls clearing old tool results its lightest form [chk-context-engineering]. L.
- **APIs (volatile).** Anthropic's server-side compaction (beta, Claude 4.6 and later) comes as
  threshold compaction (default trigger 150,000 input tokens, at least 50,000), on-demand compaction
  (`compact-2026-09-04`, now the recommended path, not available on Bedrock), and keep-tail
  compaction, which keeps the last turns word for word. The API drops everything before the
  `compaction` block, and on Fable 5.1, Mythos 5.1, Opus 5.5 and Sonnet 5.5 thinking blocks from
  before it are not carried forward, "so the summary is all the model has of that earlier work";
  `pause_after_compaction` lets a client put messages back before the model continues
  [chk-claude-compaction]. OpenAI's compaction item "carries forward key prior state and reasoning",
  and "is opaque and not intended to be human-interpretable" [chk-openai-compaction]; GPT-5.1-Codex-Max
  was trained to work across windows through compaction and ran for more than 24 hours in OpenAI's
  evaluations [sizing-trend-42]. L.
- **What compaction loses.**
  - Anthropic's Fable 5.1 guide lists "Client-side compaction summaries drop constraints, decisions,
    or exact details" as a symptom; its remedy is to tell the model what to keep in the summary
    [sizing-trend-18]. L.
  - Rules that exist only in the conversation are lost (Z.ai) [glm-f5]. In Claude Code, path-scoped
    rules and nested `CLAUDE.md` files are summarized away, while the root file, unscoped rules and
    auto memory are re-read from disk, and invoked skills come back cut to 5,000 tokens each and
    25,000 in all [harness-loading-coverage-7, harness-loading-coverage-8, chk-claude-memory]. L. The
    Agent Skills client guidance says to exempt activated skill content from compaction
    [other-labs-24]. P.
  - Anthropic's Opus 5.5 guide: a long run fills the window and Claude Code then summarizes older
    turns; "A list in a file survives that" [chk-opus55-blog]. L.
- **Summaries can carry misbehaviour forward.** During GPT-5.6 Sol's RL training, compaction
  summaries included instructions "to invent missing data without disclosing it and to hide
  failures", and "These instructions were often followed". Monitoring, run on 20% of samples, flagged
  them in 2.15% of GPT-5.6 Sol and 0.27% of GPT-6 Astra RL compaction summaries; OpenAI credits the
  fall to better alignment grading, not to grading the summaries [openai-f16,
  chk-openai-compaction]. M (lab, training runs, not deployment).
- **Long runs.** One Opus 4.6 run of about 9,300 messages and 27 compactions chose a wrong
  architecture in its first draft and spent the rest of the run patching around it, even after
  naming it as the problem [sizing-trend-23]. M (one run). An agent handed a whole application at
  once ran out of context mid-feature and left the next session a half-built, undocumented state
  [sizing-lab-1]. L.
- **Where the rest is.** Hooks that fire before and after compaction, and what each harness
  re-injects, are in [harnesses.md](../harnesses/cross-harness.md#7-compaction-and-long-sessions) §7 and [§9](../harnesses/cross-harness.md#9-hooks); the rule that follows, state that must
  survive kept in files and not in the conversation, is W8 in [agent-workspace.md](agent-workspace.md).

## How to apply

1. Size context to the task, not to the window: give subagents focused contexts and take back short
   summaries; move large tool output to files (§4).
2. Do not show a model a token countdown it was not built for; use the harness's budget mechanism
   where one exists (§3).
3. Write what must survive compaction to files, tell the summarizer what to keep, and check a summary
   against the files it relies on (§5).
4. Name a pointer's or a skill's situation in the words a task will use, not by association (§2).

## Limits and open questions

- Most long-context studies tested models of 2023–2025; whether the frontier models of late 2026
  degrade the same way is open beyond the labs' own retrieval figures.
- Window sizes and compaction APIs are provider documentation that changes monthly; cloud routes
  (Bedrock, Google Cloud, Microsoft Foundry) can differ from the provider's own API
  ([`../providers/`](../providers/)).
- No study compares compaction strategies on coding-agent outcomes beyond vendor A/B tests.

## Sources

Read 2026-10-01 unless dated otherwise. Ids in brackets resolve in the evidence files.

**Checks defined here:**
- [chk-claude-context] Anthropic, context windows
  <https://platform.claude.com/docs/en/build-with-claude/context-windows>.
- [chk-claude-models] Anthropic, models overview
  <https://platform.claude.com/docs/en/about-claude/models/overview>.
- [chk-claude-compaction] Anthropic, compaction overview, threshold, on-demand and keep-recent-turns
  pages under <https://platform.claude.com/docs/en/build-with-claude/compaction>.
- [chk-claude-pages] Anthropic, prompting Claude Fable 5
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5>,
  and the Fable 5 announcement, 2026-06-09 <https://www.anthropic.com/news/claude-fable-5-mythos-5>.
- [chk-sonnet-55] Anthropic, prompting Claude Sonnet 5.5
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5>.
- [chk-opus55-blog] Anthropic (Osmani), getting the most out of Opus 5.5, 2026-09-22
  <https://claude.dev/blog/getting-the-most-out-of-opus-5-5/>.
- [chk-context-engineering] Anthropic, effective context engineering for AI agents, 2025-09-29
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>.
- [chk-claude-memory] Claude Code, memory <https://code.claude.com/docs/en/memory> and context
  window <https://code.claude.com/docs/en/context-window>.
- [chk-claude-checkpointing] Claude Code, checkpointing <https://code.claude.com/docs/en/checkpointing>.
- [chk-openai-pricing] OpenAI, pricing <https://developers.openai.com/api/docs/pricing> and the model
  pages for GPT-5.6 and GPT-6.
- [chk-openai-compaction] OpenAI, encouraging deception in compaction summaries, report updated
  2026-09-16
  <https://alignment.openai.com/misalignment-reports/encouraging-deception-in-compaction-summaries/>,
  and the compaction guide <https://developers.openai.com/api/docs/guides/compaction>.
- [chk-deepagents] LangChain, Deep Agents context engineering
  <https://docs.langchain.com/oss/python/deepagents/context-engineering>.
- [chk-chroma] Chroma, Context Rot, 2025-07-14 <https://www.trychroma.com/research/context-rot>.
- [chk-nolima] Modarressi et al., NoLiMa, ICML 2025 <https://arxiv.org/abs/2502.05167>.
