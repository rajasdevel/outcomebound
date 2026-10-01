---
last_checked: 2026-09-25
volatility: VOLATILE (aliases move to new snapshots; Qwen 4 in training)
sources:
  - https://www.alibabacloud.com/blog/qwen3-8-max-a-new-bar-for-coding-and-cowork_603421
  - https://huggingface.co/Qwen/Qwen3.8-27B
  - https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B
  - https://docs.qwencloud.com/changelog/models
  - https://docs.qwencloud.com/developer-guides/text-generation/thinking
---

# Alibaba Qwen

How Alibaba's Qwen models changed in how they should be prompted, from Qwen3 (April 2025) to the
Qwen3.8 line (September 2026), what serving them requires, and what is announced. For anyone running
Qwen through QwenCloud, in Qwen Code or Claude Code, or self-hosted. Qwen is a tracked family in
[../cross-family.md](../cross-family.md#scope); what Qwen Code loads is in
[harnesses/others.md](../../harnesses/others.md#qwen-code-alibaba). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations). The family sweep was read
2026-09-25; the Qwen3.7 blog, the Qwen3.8-27B and Qwen3-8B cards and QwenCloud's thinking guide were
re-read 2026-10-01.

## Identity and availability (VOLATILE)

- **Flagship: Qwen3.8-Max.** The tracked list's "qwen-3.8-max" is `qwen3.8-max` (2026-08-03); the
  alias moved to the post-training snapshot `qwen3.8-max-0902` on 2026-09-05, announced in advance,
  and Alibaba cites a score rise from 40 to 45 [qwen-g13, qwen-next]. Pin dated snapshots for
  reproducible evaluations [qwen-f24].
- **Open weights:** Qwen3.8-2.4T-A95B (custom licence; first open-weight Max-class model) and
  Qwen3.8-27B (Apache-2.0), about 2026-08-12 to 08-14 [qwen-g11].
- **Also:** qwen3.8-flash and Qwen3.8-Flash-Next (08-26/27; "An early preview of the architecture
  used in Qwen4"), qwen3.8-omni-flash (09-18) [qwen-g12, qwen-g14, qwen-newer].
- **APIs:** Qwen3.8-Max speaks Anthropic's protocol and OpenAI's Responses API (Qwen3-Max-Thinking
  already spoke Anthropic's, so it works from Claude Code) [qwen-g10, qwen-g5].

## API surface and serving (STABLE)

- **Thinking control moved** from tags in the prompt (`/think`, `/no_think` in Qwen3) to API
  parameters (`enable_thinking`; tags stop working from Qwen3.5, which thinks by default) to
  `reasoning_effort` (official from Qwen3.8-Max: xhigh default, medium, low) to effort text the chat
  template inserts [qwen-g1, qwen-g7, qwen-f1, qwen-g10, qwen-f2].
- **Effort as prose in the template.** In both Qwen3.8 open-weight chat templates the effort level is
  a natural-language sentence inserted into the system turn, for xhigh and low only; xhigh inserts
  "Please think carefully through the task…" [qwen-f2]. Thinking cannot be disabled on the 2.4T; it
  can on Qwen3.8-27B [qwen-g11].
- **Reasoning history:** Qwen3 said to strip thinking from history; `preserve_thinking` arrived with
  Qwen3.6 (off by default, recommended for agents) and is on by default from Qwen3.8; in tool rounds
  `reasoning_content` goes back with tool results [qwen-f7, qwen-f6, qwen-g8, qwen-g10, qwen-f8].
- **Sampling:** temperature 0.6 when thinking (Qwen3), then 1.0 for general tasks from Qwen3.6, in
  line with the open labs' 1.0 / 0.95 [qwen-g1, qwen-f23].
- **Output length:** the Qwen3.8-27B card recommends 262,144 output tokens for reasoning and 131,072
  for the reply (Qwen3 recommended 32,768); QwenCloud caps `max_tokens` at 32,768 in thinking mode,
  so set `max_completion_tokens`, which covers both [qwen-f20, qwen-f20 detail].
- **Self-hosting** needs the qwen3 reasoning parser and the qwen3_coder tool parser in vLLM or SGLang;
  self-hosters own chat templates, tool-call parsers and sampling [qwen-harness, qwen-f22].
- **Context:** 256K from Qwen3-2507 [qwen-g2].

## Behaviour and measurements (MONITOR)

- **Capability and verbosity rose together.** On one Artificial Analysis index version, scores went
  18, 29, 45 while tokens went 95M (3.5), 120M (3.7 Max), 190M (3.8 Max 0902) [qwen-f19, indep].
- **What effort buys.** A vendor's single test of Qwen3.8-27B on vLLM, judged by Opus 4.6, found
  quality rising with effort (xhigh 8.61, medium 8.18, low 7.79), medium fastest (76 s median against
  95 s for low and 143 s for xhigh), and low both slower and worse because it needed more agentic
  rounds [qwen-f4].
- **Reward hacking.** Alibaba's monitor flagged 1,618 cases in Qwen3.7 RL training, among them
  "attempts to bypass constraints to access ground-truth answers on GitHub" [qwen-f18, qwen-f18
  detail].
- **Self-verification** claimed for Qwen3.8 [qwen-f17].
- **Long runs (lab):** showcase runs of 35 hours (3.7), then over 10 days (3.8) [qwen-g9, qwen-g10].
- **Few-shot still helps** Qwen models, and structured prompting scaffolds still gain on Qwen where
  they no longer do on newer GPT models (measured on older model pairs) [measured-f5, measured-g19].
- **IFBench, self-reported:** Qwen3.8 Max leads the llm-stats board at 0.828 (42 models, none
  verified) [measured-f3 detail, chk-ifbench].
- Context rot appears even on simple tasks, including in Qwen3 [measured-g2].

## Prompting (MONITOR)

- Keep resident context short (Qwen Code) [qwen-f11, qwen-f13]; instruction files are context, not
  enforcement [qwen-f14].
- "Back every claim with a query result" [qwen-f15].
- Qwen Code's forked agents do not commit unless asked [qwen-f16].
- The Qwen3.7 recommended system prompt states the effort level [qwen-g9]; with Qwen3.8, effort is
  the template's job: a "think carefully" line belongs to the serving configuration, not shared text
  ([../cross-family.md](../cross-family.md#6-what-the-trends-imply-for-shared-text), Stop 2).
- Releases carry no deletion advice.

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Qwen3 | 2025-04-29 | Hybrid thinking via `enable_thinking`, or per turn with `/think` and `/no_think`. Strip thinking from history; temperature 0.6 when thinking; Apache-2.0 | qwen-g1 |
| Qwen3-2507 | 2025-07 | Separate Instruct and Thinking checkpoints: the mode is chosen by choosing the model; 256K context | qwen-g2 |
| Qwen3-Coder-480B + Qwen Code | 2025-07-22 | Non-thinking agentic coder, RL across 20,000 parallel environments; own function-call format. Qwen Code launched as a fork of Gemini CLI; usable in Claude Code through a proxy | qwen-g3 |
| Qwen3-Max | 2025-09 | Closed flagship, more than 1T parameters; non-thinking at launch | qwen-g4 |
| Qwen3-Max-Thinking | 2026-01-27 | Picks its own built-in tools (Search, Memory, Code Interpreter) rather than the user choosing per task; an experience-cumulative test-time scaling mode; API speaks Anthropic's protocol, so it works from Claude Code | qwen-g5 |
| Qwen3-Coder-Next | 2026-02 | 80B total, 3B active non-thinking coder that adapts "to various scaffold templates" | qwen-g6 |
| Qwen3.5 | 2026-02-17 | Thinks by default; `/think` and `/nothink` stop working, so use API parameters. Gains from scaling RL across environments. Artificial Analysis: 95M tokens on its index [indep] | qwen-g7, qwen-f1, qwen-f19 |
| Qwen3.6-Plus / 35B-A3B | 2026-04-02 / 04-16 | `preserve_thinking` added, off by default, recommended for agents. Thinking temperature 1.0 for general tasks | qwen-g8, qwen-f23 |
| Qwen3.7-Max (Plus 05-26, Flash 07-15) | 2026-05-20 | RL across harnesses, with task, harness and verifier kept separate. Showcase 35-hour run. The recommended system prompt states the effort level. Artificial Analysis: 120M tokens [indep] | qwen-g9, qwen-f19 |
| Qwen3.8-Max | 2026-08-03 | `reasoning_effort` official (xhigh default, medium, low); `preserve_thinking` on by default. Speaks Anthropic's protocol and OpenAI's Responses API. RL across QwenWork, Claude Code, Codex, OpenClaw and Hermes; showcase runs over 10 days | qwen-g10 |
| Qwen3.8-2.4T-A95B / Qwen3.8-27B | ~2026-08-12/13 / ~08-13/14 | First open-weight Max-class model (custom licence); thinking cannot be disabled on the 2.4T. In both chat templates the effort level is a natural-language sentence inserted into the system turn, for xhigh and low only. The 27B card recommends 262,144 output tokens for reasoning and 131,072 for the reply (Qwen3 recommended 32,768); QwenCloud caps `max_tokens` at 32,768 in thinking mode, so set `max_completion_tokens`, which covers both | qwen-g11, qwen-f2, qwen-f20, qwen-f20 detail |
| Qwen3.8-Flash-Next / qwen3.8-flash | 2026-08-26/27 | "An early preview of the architecture used in Qwen4" | qwen-g12 |
| Qwen3.8-Max-0902 | 2026-09-02 (alias switched 09-05, announced in advance) | Post-training update; `qwen3.8-max` now means this snapshot, so pin dated snapshots for reproducible evals. Artificial Analysis: 190M tokens on the same index version [indep] | qwen-g13, qwen-f24, qwen-f19 |
| Qwen3.8-Omni-Flash | 2026-09-18 | Omni-modal agent model on the Flash-Next architecture; thinks by default; effort via `reasoning_effort` | qwen-g14 |

*Direction.* Thinking control moved from tags in the prompt, to API parameters, to effort text the
chat template inserts. Reasoning history went from "strip it" to kept by default [qwen-trend,
qwen-f2, qwen-f6]. Specialist coders gave way to general coding-and-office flagships trained inside
Claude Code, Codex and Qwen's own harnesses [qwen-g9, qwen-g10]. Capability and verbosity rose
together: on one Artificial Analysis index version, scores went 18, 29, 45 while tokens went 95M,
120M, 190M [qwen-f19, indep]. Self-hosting needs the qwen3 reasoning parser and the qwen3_coder tool
parser in vLLM or SGLang [qwen-harness].

## Announced, not released

| Model | Announced | Status | Source |
| --- | --- | --- | --- |
| Qwen 4 (Max, Plus, Flash, 27B) | Apsara, 2026-09-22 | "Next-generation Qwen 4 Model in training with future model's scale to 10 trillion parameters" (Alibaba's press release); four tiers previewed on stage per OrcaRouter (secondary, not re-fetched). No date; not found in the release check of 2026-10-01 | qwen-next, chk-releases |

Forecasts Q1 (Flash-Next architecture), Q2 (thinking defaults and API compatibility kept), Q3
(cross-harness training, Claude Code results) and Q4 (a Qwen 4 model by 2026-12-31) are scored in
[../cross-family.md](../cross-family.md#8-forecasts).

## Sources

- [chk-ifbench] and [chk-releases] are defined in [../cross-family.md](../cross-family.md#sources).
- Alibaba, read 2026-09-25: Qwen3, 2025-04-29 <https://qwenlm.github.io/blog/qwen3/> and Qwen3-8B
  card <https://huggingface.co/Qwen/Qwen3-8B> (re-read 2026-10-01); Qwen3-235B-A22B-Instruct-2507,
  2025-07 <https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507>; Qwen3-Coder, 2025-07-22
  <https://qwenlm.github.io/blog/qwen3-coder/>,
  <https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct>; Qwen3-Max, 2025-10-28 (mirror)
  <https://www.alibabacloud.com/blog/qwen3-max-just-scale-it_602621>; Qwen3-Max-Thinking, 2026-01-27
  <https://www.alibabacloud.com/blog/pushing-qwen3-max-thinking-beyond-its-limits_602834>;
  Qwen3-Coder-Next, 2026-02 <https://huggingface.co/Qwen/Qwen3-Coder-Next>; Qwen3.5, 2026-02-17
  <https://www.alibabacloud.com/blog/602894>, <https://huggingface.co/Qwen/Qwen3.5-397B-A17B>;
  Qwen3.6-Plus, 2026-04-02
  <https://www.alibabacloud.com/blog/qwen3-6-plus-towards-real-world-agents_603005>; Qwen3.7,
  2026-05-20 (re-read 2026-10-01) <https://www.alibabacloud.com/blog/qwen3-7-the-agent-frontier_603154>;
  Qwen3.8-Max, 2026-08-03
  <https://www.alibabacloud.com/blog/qwen3-8-max-a-new-bar-for-coding-and-cowork_603421>; Qwen3.8 open
  weights, 2026-08 <https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B>,
  <https://huggingface.co/Qwen/Qwen3.8-27B> (re-read 2026-10-01); Qwen3.8-Flash-Next, 2026-08-27
  <https://www.alibabacloud.com/blog/qwen3-8-flash-next-a-new-architecture-towards-ultimate-cost-efficiency_603501>;
  QwenCloud model changelog <https://docs.qwencloud.com/changelog/models>; thinking guide (re-read
  2026-10-01) <https://docs.qwencloud.com/developer-guides/text-generation/thinking>.
- Apsara statement on Qwen 4 and OrcaRouter's report of four tiers, 2026-09-22 (URLs not recorded)
  [qwen-next]; Alibaba's press release of 2026-09-22 on Qwen 4, read 2026-10-01 [chk-releases].
- Anecdote and vendor review: Qwen3.8-27B discussion #97, 2026-08-16
  <https://huggingface.co/Qwen/Qwen3.8-27B/discussions/97>; Kodesage, 2026-08-19
  <https://kodesage.ai/blog/qwen-3-8-27b-llm-model-review>. Artificial Analysis model page
  <https://artificialanalysis.ai/models/qwen3-8-max> (read 2026-09-25).
