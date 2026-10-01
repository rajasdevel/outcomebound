---
last_checked: 2026-10-01
volatility: VOLATILE (Haiku 5.5 announced without a date; Haiku 4.5 retirement pending)
sources:
  - https://platform.claude.com/docs/en/about-claude/models/overview
  - https://platform.claude.com/docs/en/models/haiku-4-5/migration-guide
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  - https://www.anthropic.com/claude-sonnet-5-5
  - https://www.anthropic.com/news/claude-opus-5-5
---

# Claude Haiku

What Anthropic's smallest current model is, what guidance exists for it, and what is announced. For
anyone choosing a cheap tier for subagents or high-volume work, or checking whether text trimmed for
frontier Claude models says enough for it. Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and availability (VOLATILE)

- **Haiku 4.5** (`claude-haiku-4-5`, snapshot `claude-haiku-4-5-20251001`; released 2025-10-15) is
  the current Haiku: 200K context, 64K output, $1 / $5 per MTok, extended thinking with a manual
  budget, no effort parameter, knowledge cutoff Feb 2025, comparative latency "Fastest"
  [claude-g3, chk-claude-models]. It is to be retired no sooner than 2026-10-15 [claude-newer,
  chk-releases].
- It accepts `temperature`, `top_p` and `top_k`, which Sonnet 5 and later reject. Its thinking
  blocks can be read by Sonnet 5.5. Minimum cacheable prompt 4,096 tokens
  ([practices/prompt-caching.md](../../practices/prompt-caching.md#2-anthropic-volatile)); it receives API-injected context-awareness tags
  ([practices/long-context-and-compaction.md](../../practices/long-context-and-compaction.md#3-context-awareness-countdowns-and-early-wrap-up-volatile)).
- **Haiku 5.5** was announced with Opus 5.5 on 2026-09-22 and again on 2026-09-28: it "will join the
  Claude 5.5 family in the coming weeks"; no date, price or model id. It was not found in the release
  check of 2026-10-01 [chk-anthropic-55, chk-sonnet-55, claude-next, chk-releases].

## Prompting (MONITOR)

- **No Haiku-specific guide.** Anthropic's prompting best practices cover models through Haiku 4.5
  and say that where a technique names a specific model it was measured on that model: re-check it
  against your own evaluations before applying it to Haiku [capability-tier-readers-9]. Haiku 4.5
  had no prompting page of its own [claude-g3].
- **Where it fits.** Anthropic measured Haiku 4.5 far behind Opus 5.5 on long coding tasks and places
  it for high-volume work with checkable outputs rather than long agentic loops
  [capability-tier-readers-11].
- **Smaller tiers in general** may need more explicit text than a flagship: text trimmed for
  frontier readers can say too little for them; that question is `UNVERIFIED` for Claude
  ([../cross-family.md](../cross-family.md#5-divergences-that-matter-for-text-shared-across-families-volatile),
  "Smaller tiers").
- Claude Code's built-in Explore subagent ran on Haiku until v2.1.198; from that version it inherits
  the main conversation's model, capped at Opus on the Claude API [chk-claude-subagents].

## Forecasts on Haiku

Scored in [../cross-family.md](../cross-family.md#8-forecasts):
- **A1b** Haiku 5.5 is generally available by 2026-11-30 (medium).
- **A3, Haiku half** thinking cannot be disabled on Haiku 5.5 (low); open.
- **A4b** Haiku 5.5 ships with its own prompting page with removal advice (medium-low).

## Lineage

Haiku 4.5 shipped on 2025-10-15, two weeks after Sonnet 4.5 (2025-09-29), whose release brought
context tracking and the Agent SDK ([earlier-generations.md](earlier-generations.md)) [claude-g3].
Haiku was last refreshed in October 2025 [claude-newer].

## Sources

- [chk-claude-models] is defined in [claude-5-family-prompting.md](claude-5-family-prompting.md#sources);
  [chk-anthropic-55] in [opus.md](opus.md#sources); [chk-sonnet-55] in [sonnet.md](sonnet.md#sources);
  [chk-claude-subagents] and [chk-releases] in [../cross-family.md](../cross-family.md#sources).
- Haiku 4.5 migration guide, read 2026-10-01
  <https://platform.claude.com/docs/en/models/haiku-4-5/migration-guide>.
