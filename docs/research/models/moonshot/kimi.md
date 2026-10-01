---
last_checked: 2026-09-25
volatility: VOLATILE (open-weight releases every one to three months)
sources:
  - https://huggingface.co/moonshotai/Kimi-K3
  - https://github.com/MoonshotAI/Kimi-K3
  - https://arxiv.org/html/2607.24653
  - https://huggingface.co/moonshotai/Kimi-K2.7-Code/raw/main/README.md
---

# Moonshot Kimi

How Moonshot's Kimi models changed in how they should be prompted and served, from Kimi K2 (July
2025) to Kimi K3 (July 2026). For anyone running Kimi through Moonshot's API, in Kimi Code or Claude
Code, or self-hosted. Moonshot sits outside the tracked list of
[../cross-family.md](../cross-family.md#scope), among "the other labs"; the research recommends
tracking it. What Kimi Code loads is in [harnesses/others.md](../../harnesses/others.md#kimi-code-moonshot). Labels and ids as
in [../cross-family.md](../cross-family.md#evidence-labels-and-citations); the Kimi K3 card was
re-read 2026-10-01.

## Identity and API (VOLATILE)

- **Current: Kimi K3**, hosted 2026-07-16, weights 2026-07-27 [open-weight-g14].
- **Always thinks**; `reasoning_effort` low, high, max, default max [open-weight-g14].
- **The API must receive the full reasoning history** on K3; K2.7 Code forces thinking and preserved
  thinking on [open-weight-g14, open-weight-g13].
- Recommended sampling: temperature 1.0 (K2 Thinking), 0.6 for the non-thinking K2-Instruct
  [open-weight-g4, open-weight-g1]; the open labs converge on 1.0 and top_p 0.95
  [open-weight-harness].
- Moonshot tells Claude Code users to set `CLAUDE_CODE_AUTO_COMPACT_WINDOW` to its 1M window
  [open-weight-f14 detail].

## Behaviour and measurements (MONITOR)

- **Trained across harnesses:** RL in configurations imitating Kimi Code, Claude Code, Codex,
  OpenClaw and Hermes [open-weight-g14]. Kimi reports K3 slightly higher in Claude Code (73.7) than
  in its own Kimi Code (72.9) on its own benchmark [lab; open-weight-f2 detail].
- **Tools.** Cutting K3's tools from 28 to 11 cut output tokens by 20.3% at the same pass rate (small
  sample) [open-weight-f15].
- **Long runs (lab):** K2 Thinking coherent across 200–300 tool calls; K2.6 showcase runs of 12–13
  hours with 1,000+ tool calls; K2.5 directs its own swarm of up to 100 subagents [open-weight-g4,
  open-weight-g10, open-weight-g7].
- **Benchmarks.** SWE-Bench Pro V2 (Scale): Kimi K3 88.2, level with Sonnet 5 [measured-g22]. In
  DeepSeek's table, Terminal-Bench 4.0: K3 12.6 against 51.8 for Opus 5; TB 2.1 (saturated): K3 88.3
  [open-weight-f20, open-weight-f20 detail]. Instruction half-life for multiple constraints on one
  output: Kimi K2.6 at 1, against GPT-5.5 at 7 and Opus 4.7 at 6 [measured-g16].
- **Kimi Code** reminds the model to re-read `AGENTS.md` [open-weight-f8].

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Kimi K2-Instruct | 2025-07-11 | Non-thinking "reflex-grade" model; temperature 0.6 | open-weight-g1 |
| K2 Thinking | 2025-11-04 | Reasoning interleaved with tools; coherent across 200–300 tool calls; temperature 1.0 | open-weight-g4 |
| K2.5 | ~2026-01-22 | Directs its own swarm of up to 100 subagents | open-weight-g7 |
| K2.6 | ~2026-04-20 | Showcase runs of 12–13 hours with 1,000+ tool calls | open-weight-g10 |
| K2.7 Code | 2026-06-11 | Thinking and preserved thinking forced on; about 30% fewer thinking tokens than K2.6 | open-weight-g13 |
| K3 | 2026-07-16 hosted; weights 07-27 | Always thinks; `reasoning_effort` low/high/max, default max. The API must receive the full reasoning history. RL in configurations imitating Kimi Code, Claude Code, Codex, OpenClaw and Hermes | open-weight-g14 |

The direction shared with the other open-weight labs is in
[../other/open-weight-labs.md](../other/open-weight-labs.md#direction-across-open-weight-labs-stable).

## Sources

Read 2026-09-25 unless dated otherwise: Kimi K2-Instruct, 2025-07-11
<https://huggingface.co/moonshotai/Kimi-K2-Instruct/raw/main/README.md>; Kimi K2 Thinking,
2025-11-04 <https://huggingface.co/moonshotai/Kimi-K2-Thinking/raw/main/README.md>; Kimi K2.5,
~2026-01-22 <https://www.kimi.ai/blog/kimi-k2-5>; Kimi K2.6, ~2026-04-20
<https://www.kimi.ai/blog/kimi-k2-6>; Kimi K2.7 Code, 2026-06-11
<https://huggingface.co/moonshotai/Kimi-K2.7-Code/raw/main/README.md>; Kimi K3, 2026-07-27
<https://github.com/MoonshotAI/Kimi-K3>, <https://arxiv.org/html/2607.24653>, card (re-read
2026-10-01) <https://huggingface.co/moonshotai/Kimi-K3>; practitioner test, small sample,
2026-07-31, Kimi K3 in Claude Code
<https://newsletter.ownersnotrenters.com/p/putting-kimi-k3-to-the-claude-code>.
