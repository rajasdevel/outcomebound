---
last_checked: 2026-09-25
volatility: MONITOR (release cadence about one to three months)
sources:
  - https://www.minimax.io/blog/minimax-m3
  - https://platform.minimax.io/docs/release-notes/models
  - https://platform.minimax.io/docs/token-plan/prompting-best-practices
---

# MiniMax

How MiniMax's models changed in how they should be prompted and served, from M2 (October 2025) to M3
(June 2026), and what MiniMax's own prompting guide says. For anyone running MiniMax in a coding
harness or through its API. MiniMax sits outside the tracked list of
[../cross-family.md](../cross-family.md#scope), among "the other labs". Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and API (VOLATILE)

- **Current: MiniMax M3** (2026-06-01): thinking switchable; trained against a simulated user to
  clarify, take correction and switch tasks [open-weight-g11].
- **Reasoning must be passed back.** From M2 the model reasons between tool calls, so the harness
  keeps full history including thinking; MiniMax attributes "much" reported underperformance to
  dropping it [open-weight-g3, open-weight-f9].
- Sampling: the open labs' temperature 1.0 and top_p 0.95 [open-weight-harness].

## Behaviour and measurements (MONITOR)

- **M2.1** claims reliable support for other tools' instruction files (Claude.md, agent.md,
  cursorrule, Skill.md, slash commands), better "composite instruction constraints", and stable
  results in Claude Code, Droid, Cline, Kilo Code, Roo Code and BlackBox [open-weight-g6].
- **M2.7** is "beginning the journey of recursive self-improvement", running more than 100 autonomous
  rounds of modifying its own scaffold code [open-weight-g8].
- **OctoBench (co-authored by MiniMax):** the system prompt and the user override project documents;
  every model except Opus 4.5 decays over a session; MiniMax-M2.1 was comparatively stable across
  harnesses [open-weight-f5, open-weight-f8, open-weight-f24].

## Prompting (MONITOR)

- **MiniMax's prompting guide mirrors Anthropic's** [open-weight-f12]; its frame is Task / Context /
  Constraints / Output [open-weight-f22].
- Use tools only when they materially improve the answer, confirm before destructive actions or
  external writes, and stop after repeated failures [open-weight-f13].
- Keep always-loaded text short; effort is the thinking control [open-weight-f10].
- In harnesses that compress context, keep system prompts concise, because "The model may terminate
  tasks early when approaching context capacity thresholds" [open-weight-f14].

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| M2 | 2025-10-27 | Reasons between tool calls, so the harness must keep full history including thinking; MiniMax attributes "much" reported underperformance to dropping it | open-weight-g3 |
| M2.1 | 2025-12-22 | Claims reliable support for other tools' instruction files (Claude.md, agent.md, cursorrule, Skill.md, slash commands), better "composite instruction constraints", and stable results in Claude Code, Droid, Cline, Kilo Code, Roo Code and BlackBox | open-weight-g6 |
| M2.5 / M2.7 | 2026-02 / 2026-03-18 | M2.5 targets coding, tools, search and office work; M2.7 is "beginning the journey of recursive self-improvement", running more than 100 autonomous rounds of modifying its own scaffold code | open-weight-g8 |
| M3 | 2026-06-01 | Thinking switchable; trained against a simulated user to clarify, take correction and switch tasks | open-weight-g11 |

The direction shared with the other open-weight labs is in
[../other/open-weight-labs.md](../other/open-weight-labs.md#direction-across-open-weight-labs-stable).

## Sources

Read 2026-09-25: MiniMax on M2, 2025-10-30 <https://huggingface.co/blog/MiniMax-AI/aligning-to-what>;
MiniMax M2.1, 2025-12-23 <https://www.minimax.io/news/minimax-m21>; MiniMax release notes, 2026-03-18
<https://platform.minimax.io/docs/release-notes/models>; MiniMax M3, 2026-06-01
<https://www.minimax.io/blog/minimax-m3>; MiniMax prompting best practices (undated)
<https://platform.minimax.io/docs/token-plan/prompting-best-practices>; OctoBench (co-authored by
MiniMax), 2026-01-15 <https://arxiv.org/html/2601.10343>.
