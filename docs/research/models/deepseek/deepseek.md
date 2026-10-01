---
last_checked: 2026-09-25
volatility: VOLATILE (V4.1-Pro confirmed but undated)
sources:
  - https://api-docs.deepseek.com/news/news260813
  - https://arxiv.org/html/2609.19969
  - https://arxiv.org/html/2606.19348v1
  - https://api-docs.deepseek.com/news/news260424
---

# DeepSeek

How DeepSeek's models changed in how they should be prompted and served, from DeepSeek-R1 (January
2025) to V4.1-Flash (September 2026), and what is announced. For anyone running DeepSeek through its
API, in Claude Code, Codex or DeepSeek Harness, or self-hosted. DeepSeek sits outside the tracked
list of [../cross-family.md](../cross-family.md#scope), among "the other labs". What DeepSeek Harness
loads is in [harnesses/others.md](../../harnesses/others.md#deepseek-harness-dsh-developer-preview-mit). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations); the V4 and V4.1-Flash
reports were re-read 2026-10-01.

## Identity and API (VOLATILE)

- **Current:** V4-Pro (GA 2026-08-13) and V4.1-Flash (2026-09-10); MIT licence [open-weight-g15,
  open-weight-g17].
- **Effort:** low, high, max on V4-Pro, default high; on V4.1-Flash a number from 1 to 100
  [open-weight-g15, open-weight-g17, open-weight-f10].
- **Thinking can be switched off;** thinking mode ignores temperature; reasoning is kept across user
  turns in tool use and must be passed back [open-weight-g2, open-weight-harness, open-weight-g9,
  open-weight-g3].
- **API formats:** Anthropic's (from V3.1, so a drop-in for Claude Code, OpenClaw and OpenCode) and
  OpenAI's Responses API with one-click Codex setup (V4-Pro) [open-weight-g2, open-weight-g9,
  open-weight-g15].
- **Context:** 1M by default from V4 Preview [open-weight-g9]. DeepSeek tells Claude Code users to
  set `CLAUDE_CODE_AUTO_COMPACT_WINDOW` to its 1M window [open-weight-f14 detail].
- **DeepSeek Harness** says instruction files "do not override system, developer, or direct user
  instructions" [open-weight-harness].

## Behaviour and measurements (MONITOR)

- **Harness spread (lab).** DeepSeek's own table spreads about 9 points across eight scaffold
  configurations (DeepSWE v1.1, 65.5 to 74.2; 6.5 points on Terminal-Bench 2.1), the minimal
  scaffolds scoring highest. By harness, on DeepSWE v1.1: Claude Code 69.8 (68.9 averaged over four
  Claude Code versions), Codex 65.6, OpenCode 65.5, Pi 66.2, mini-SWE 74.2 and DeepSeek's minimal
  harness 72.6 [open-weight-f2, open-weight-f2 detail].
- **Against Opus 5 (DeepSeek's table).** Terminal-Bench 4.0: V4.1-Flash 31.2 against Opus 5 51.8;
  the same table has V4.1-Flash ahead of Opus 5 on DeepSWE v1.1 and on TB 2.1, which it shows
  saturated (V4.1-Flash 90.6, Opus 5 89.1) [open-weight-f20, open-weight-f20 detail].
- **V4 Preview (lab).** In DeepSeek's survey of 85 of its own developers, 52% said V4-Pro was ready to
  be their default coding model and 39% leaned that way; respondents noted trivial mistakes, misread
  vague prompts and occasional over-thinking. DeepSeek says it "occasionally overlooks specific
  formatting constraints", and in its internal pairwise test of complex instruction following (49
  items) V4-Pro won 46.9% against Opus 4.5's 53.1% [open-weight-g9, open-weight-f16, open-weight-f16
  detail].
- **Instruction capacity (indep):** DeepSeek V4 Pro dropped from about 750 simultaneous named items
  [measured-g10]. An Artificial Analysis snapshot of 2026-04-30 put DeepSeek V4 Pro 3–6 points behind
  GPT-5.5 on its Intelligence Index [open-weight-f21].
- **Few-shot prompting degrades DeepSeek-R1** (2025-01) [research-24].

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| V3.1 | 2025-08-21 | Think and non-think modes in one model; Anthropic API format | open-weight-g2 |
| V3.2 | 2025-12-01 | Thinking inside tool use; 1,800+ synthetic environments | open-weight-g5 |
| V4 Preview | 2026-04-24 | 1M context by default; keeps reasoning across user turns in tool use; drop-in for Claude Code, OpenClaw and OpenCode. In DeepSeek's survey of 85 of its own developers, 52% said V4-Pro was ready to be their default coding model and 39% leaned that way; respondents noted trivial mistakes, misread vague prompts and occasional over-thinking. DeepSeek says it "occasionally overlooks specific formatting constraints", and in its internal pairwise test of complex instruction following (49 items) V4-Pro won 46.9% against Opus 4.5's 53.1% [lab] | open-weight-g9, open-weight-f16, open-weight-f16 detail |
| V4-Pro GA | 2026-08-13 | Effort low/high/max; native OpenAI Responses API with one-click Codex setup | open-weight-g15 |
| V4.1-Flash | 2026-09-10 | RL across four Claude Code versions plus OpenCode, Pi and DeepSeek Harness; effort a number from 1 to 100; about a 9-point spread across harnesses in DeepSeek's table | open-weight-g17 |

## Announced, not released

| Model | Announced | Status | Source |
| --- | --- | --- | --- |
| DeepSeek V4.1-Pro | 2026-09 | Confirmed, undated ("This will continue until V4.1-Pro launches"); not found in the release check of 2026-10-01 | open-weight-next, chk-releases |

Forecast D1 (V4.1-Pro released by 2026-12-31) is scored in
[../cross-family.md](../cross-family.md#8-forecasts). The direction shared with the other
open-weight labs is in
[../other/open-weight-labs.md](../other/open-weight-labs.md#direction-across-open-weight-labs-stable).

## Sources

- [chk-releases] is defined in [../cross-family.md](../cross-family.md#sources).
- Read 2026-09-25 unless dated otherwise: DeepSeek-R1, 2025-01-22 <https://arxiv.org/html/2501.12948v1>;
  DeepSeek V3.1, 2025-08-21 <https://api-docs.deepseek.com/news/news250821>; DeepSeek V3.2,
  2025-12-01 <https://api-docs.deepseek.com/news/news251201>; DeepSeek V4 Preview, 2026-04-24
  <https://api-docs.deepseek.com/news/news260424>, V4 report, 2026-04-26 (re-read 2026-10-01)
  <https://arxiv.org/html/2606.19348v1>; DeepSeek V4-Pro GA, 2026-08-13
  <https://api-docs.deepseek.com/news/news260813>; DeepSeek V4.1 report, 2026-09-17 (re-read
  2026-10-01) <https://arxiv.org/html/2609.19969>.
- Artificial Analysis, open-weight launches, 2026-04-30
  <https://artificialanalysis.ai/articles/recent-open-weights-model-launches>.
