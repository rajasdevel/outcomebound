---
last_checked: 2026-09-25
volatility: STABLE (history; lifecycle dates in the last section are VOLATILE)
sources:
  - https://platform.claude.com/docs/en/release-notes/overview
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  - https://www.anthropic.com/news/claude-opus-4-6
  - https://www.anthropic.com/news/claude-opus-4-7
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
---

# Claude before the 5 generation: Claude 3.7 Sonnet to Opus 4.8

How Anthropic's advice for prompting Claude changed from Claude 3.7 Sonnet (February 2025) to Opus
4.8 (May 2026), and which of those models remain available. For anyone maintaining text first
written for these models, or reading why the Claude 5 guidance says what it says. The Claude 5
models are in [fable.md](fable.md), [opus.md](opus.md), [sonnet.md](sonnet.md) and
[haiku.md](haiku.md); labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Lineage (STABLE)

Each row is Anthropic's own claim unless tagged.

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Claude 3.7 Sonnet | 2025-02-24 | First hybrid reasoning model: extended thinking per request, with a manual `budget_tokens`. A high-level "think deeply" beat prescribed steps; prefill, XML tags and manual chain of thought still standard. Claude Code research preview shipped alongside | claude-g1 |
| Opus 4 / Sonnet 4 (Opus 4.1: 2025-08-05) | 2025-05-22 | "More precise instruction following". Ask explicitly for "above and beyond" work, give the reason behind a rule, say what to do rather than what not to do. 65% less likely than 3.7 to take shortcuts on shortcut-prone agentic tasks (Anthropic's evaluation) | claude-g2, claude-g1 |
| Sonnet 4.5 (Haiku 4.5: 2025-10-15) | 2025-09-29 | Tracks its remaining context, so tell it when the harness compacts. Claude Code 2.0 and the Agent SDK shipped the same day, with the advice to use "the smallest possible set of high-signal tokens". 30+ hours of sustained focus observed | claude-g3 |
| Opus 4.5 | 2025-11-24 | Effort parameter (beta). More responsive to the system prompt, so emphasis written against under-use ("CRITICAL: You MUST use this tool") now causes over-use. Tends to overengineer; Anthropic published a scope-limiting prompt | claude-g4, claude-f4 |
| Opus 4.6 (Sonnet 4.6: 2026-02-17) | 2026-02-05 | Adaptive thinking; `budget_tokens` deprecated; prefilling the last turn returns 400; compaction API beta. Explores more up front, likes subagents, takes hard-to-reverse actions unguided, so Anthropic published a reversibility prompt. If it overthinks, lower effort or constrain reasoning. For tool overuse, remove "If in doubt, use [tool]" | claude-g5 |
| Opus 4.7 | 2026-04-16 | Literal: "re-tune your prompts and harnesses". New tokenizer (1.0–1.35x more tokens). Task budgets (beta). Remove "summarize every 3 tool calls" scaffolding. `budget_tokens` returns 400 | claude-g7 |
| Opus 4.8 | 2026-05-28 | Respects effort strictly: at low and medium it does only what was asked. Does not generalize an instruction from one item to others. "Only high-severity" in review prompts now suppresses recall. Fewer subagents. System messages can be added mid-conversation without breaking the cache. About 4x less likely to let flaws in its own code pass | claude-g8, claude-f13 |

Mythos Preview (2026-04-07, gated) is in [fable.md](fable.md#lineage-volatile).

## What carried forward and what reversed (STABLE)

- **Emphasis.** From Opus 4.5 on, prompts written to fix under-triggering ("CRITICAL: You MUST use
  this tool when…", "If in doubt, use [tool]") cause over-triggering; Anthropic's best practices
  say to use plain conditions instead [claude-f4, claude-f5, anthropic-4].
- **Literalism.** More precise with Claude 4, more responsive with Opus 4.5, literal on Opus 4.7 and
  4.8 (and Sonnet 5): state when a rule covers every item [claude-g2, claude-g4, claude-g7,
  claude-g8].
- **Scope and overengineering.** Opus 4.5 and 4.6 overengineer, with published scope and
  reversibility prompts [claude-g4, claude-g5].
- **Delegation.** Opus 4.6 eager, Opus 4.8 fewer subagents, then eager again from Opus 5
  [claude-f21].
- **Thinking controls.** `budget_tokens` deprecated on Opus 4.6 and rejected from Opus 4.7;
  prefilling the last turn rejected from Opus 4.6; non-default sampling rejected from Opus 4.7.
  Opus 4.8 has thinking off unless it is set, and Anthropic's pages still suggest a "think
  carefully" line for Opus 4.8 with thinking off when effort has to stay low [claude-f2].
- **Effort.** Anthropic's Opus 4.8 page recommended `xhigh` for most coding; the Opus 5.5 page keeps
  `xhigh` and `max` for work with a measured gain [claude-f23].
- **Context awareness.** Sonnet 4.5 showed "context anxiety", wrapping up early near what it
  believed was its limit, strongly enough that Anthropic's long-running harness needed context
  resets; Opus 4.5 "largely removed" it (details in
  [practices/long-context-and-compaction.md](../../practices/long-context-and-compaction.md#3-context-awareness-countdowns-and-early-wrap-up-volatile)).

Independent figures on these models: METR put Opus 4.6's 50% time horizon at about 12 hours
[measured-g9]; OctoBench found every model except Opus 4.5 decaying in compliance over a session,
and Sonnet 4.5's rule compliance falling from 16.7% in Claude Code to 4.4% in Kilo, while Opus 4.5
stayed comparatively stable [open-weight-f8, open-weight-f24]; IFBench put Claude at 54–59%
[measured-g11]; Opus 4.7 held named-item inclusion to about 50% at 5,000 items, with API-level
refusals [measured-g10]. On an eight-needle retrieval test at 1M tokens Anthropic reported Sonnet 4.5
at 18.5% and Opus 4.6 at 76%: needles found, not instructions followed [lab; measured-f18]. One
practitioner team moved back from Opus 4.6 with a 1M window to Opus 4.5 after instruction adherence
worsened even at short lengths [A; practitioners-11]. Each is cited where it bears on a trend in
[../cross-family.md](../cross-family.md#3-trends-r1r16).

## Lifecycle (VOLATILE)

- **Legacy, still available** (models overview, 2026-10-01): Opus 4.8, Opus 4.7 and other 4.x
  models. Opus 4.8, 4.7, 4.6 and 4.5 share one combined Opus rate limit; Sonnet 4.6 and 4.5 share
  one Sonnet 4.x limit.
- **Retired:** Claude Sonnet 4 and Opus 4 on 2026-06-15; Opus 4.1 on 2026-08-05.
- **Deprecated:** Sonnet 4.5, announced 2026-09-30, retirement on the Claude API scheduled for
  2026-11-30.
- **Fast mode:** removed from Opus 4.6 on 2026-06-29 (requests run at standard speed) and from Opus
  4.7 on 2026-07-24 (requests return an error); kept on Opus 4.8.

## Sources

Anthropic, read 2026-09-25 unless dated otherwise. Claude Code best practices, 2025-04-18
(archived)
<https://web.archive.org/web/20250420034405/https://www.anthropic.com/engineering/claude-code-best-practices>;
extended thinking tips, Claude 3.7 era (archived 2025-08-06)
<https://web.archive.org/web/20250806014516/https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/extended-thinking-tips>;
Claude 4 best practices (archived 2025-08-27)
<https://web.archive.org/web/20250827210035/https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices>;
effective context engineering, 2025-09-29
<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>; Claude Opus
4.6, 2026-02-05 <https://www.anthropic.com/news/claude-opus-4-6>; harness design for long-running
apps, 2026-03-24 <https://www.anthropic.com/engineering/harness-design-long-running-apps>; Claude
Opus 4.7, 2026-04-16 <https://www.anthropic.com/news/claude-opus-4-7>; prompting best practices
(living, re-read 2026-10-01)
<https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>;
the Opus 4.8 prompting page
<https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8>;
release notes (re-read 2026-10-01) <https://platform.claude.com/docs/en/release-notes/overview>.
