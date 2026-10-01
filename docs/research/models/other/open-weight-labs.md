---
last_checked: 2026-09-25
volatility: MONITOR (open-weight releases monthly; direction stable)
sources:
  - https://developer.nvidia.com/blog/nvidia-nemotron-3-ultra-powers-faster-more-efficient-reasoning-for-long-running-agents/
  - https://huggingface.co/tencent/Hy4-preview/raw/main/README.md
  - https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Pro-RL/raw/main/README.md
  - https://artificialanalysis.ai/articles/recent-open-weights-model-launches
---

# Open-weight labs: shared direction, NVIDIA Nemotron, Tencent Hy, Xiaomi MiMo

What the open-weight agentic labs have in common in how their models are served and prompted, how
open models compare with closed ones on the same evaluator, and the three smaller lines that have
no file of their own (NVIDIA Nemotron, Tencent Hy, Xiaomi MiMo). For anyone self-hosting an open
model or choosing which open models to test shared text on. The larger open-weight families have
their own files: [../moonshot/kimi.md](../moonshot/kimi.md),
[../deepseek/deepseek.md](../deepseek/deepseek.md), [../minimax/minimax.md](../minimax/minimax.md),
[../mistral/mistral.md](../mistral/mistral.md), [../zai/glm.md](../zai/glm.md),
[../alibaba/qwen.md](../alibaba/qwen.md); the closed labs' open lines are under
[../openai/earlier-generations.md](../openai/earlier-generations.md#gpt-oss-open-weights) (gpt-oss)
and [../google/gemini.md](../google/gemini.md#gemma-open-weights) (Gemma). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Direction across open-weight labs (STABLE)

- **Reasoning is mostly on by default:** Kimi K3 and K2.7 Code force it, while MiniMax M3 and
  DeepSeek can switch it off [open-weight-g13, open-weight-g14, open-weight-g11, open-weight-g2].
- Effort settings, 1M context and APIs compatible with both Anthropic and OpenAI are common
  [open-weight-trend].
- **The labs train against other labs' harnesses,** and most open-weight benchmark tables in the
  research were run in Claude Code, by the labs' own account [open-weight-trend, open-weight-f1].
- MiniMax's prompting guide mirrors Anthropic's [open-weight-f12].
- **Serving.** These models need their reasoning passed back verbatim (K3, K2.7 Code, M2/M3, DeepSeek
  with tools), and their vendors recommend temperature 1.0 and top_p 0.95 [open-weight-harness].
  Self-hosters own chat templates, tool-call parsers and sampling; behaviour depends on the serving
  configuration, not prose.
- **Licences** (a hosting matter, not a prompting one): custom for GLM-5.3 and Qwen3.8-2.4T; MIT for
  GLM-5.3-Flash, DeepSeek and MiMo; Apache-2.0 for Qwen3.8-27B, Hy4, gpt-oss [review], Gemma 4,
  Devstral Small 2 and Mistral Large 3; modified MIT for Devstral 2 and Mistral Medium 3.5; Muse
  Spark 1.3 closed [glm-g9, glm-g10, qwen-g11, open-weight-g16, open-weight-g18, chk-gemma,
  chk-mistral-devstral2, chk-mistral-models, chk-meta].

## Open against closed on one evaluator (MONITOR)

- **SWE-Bench Pro V2** (Scale, 642 tasks, endpoint-only, re-graded): Opus 5 (Claude Code, xhigh)
  98.0, Fable 5.1 92.2, GPT-6 Astra (Codex) 90.2, Sonnet 5 88.2, Kimi K3 88.2, GLM-5.3 84.3, GPT-5.6
  Sol 82.4, Gemini 3.8 Flash 58.8 [measured-g22].
- **Terminal-Bench 4.0 in DeepSeek's table:** V4.1-Flash 31.2, K3 12.6, Opus 5 51.8; TB 2.1 is
  saturated (V4.1-Flash 90.6, Opus 5 89.1, K3 88.3) [open-weight-f20, open-weight-f20 detail].
- **Artificial Analysis, 2026-04-30:** Kimi K2.6, MiMo V2.5 Pro and DeepSeek V4 Pro 3–6 points
  behind GPT-5.5 on its Intelligence Index, with wider gaps on CritPt (4–12% against 27%) and
  TerminalBench Hard (43–46% against 61%) [open-weight-f21].
- The gap depends on the benchmark and index versions are not comparable, so no widening or
  narrowing is shown; forecast C8 is scored in [../cross-family.md](../cross-family.md#8-forecasts).

## NVIDIA, Tencent and Xiaomi (VOLATILE)

| Lab | Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- | --- |
| NVIDIA | Nemotron 3 Ultra | 2026-06-04 | Post-trained for consistency across harnesses: 65–70.4% SWE-bench Verified across five harnesses (NVIDIA's figures) | open-weight-g12 |
| Tencent | Hy4 preview | 2026-08-27 | Co-designed with CodeBuddy and WorkBuddy; known to over-reason and over-verify | open-weight-g16, open-weight-f17 |
| Xiaomi | MiMo-V2.6 Pro / Flash (and Pro-UltraSpeed) | 2026-09-22 | Harnesses mixed in each RL batch so skills carry over to harnesses not seen in training; MIT | open-weight-g18, open-weight-newer |

## Sources

- [chk-gemma] is defined in [../google/gemini.md](../google/gemini.md#sources); [chk-mistral-devstral2]
  and [chk-mistral-models] in [../mistral/mistral.md](../mistral/mistral.md#sources); [chk-meta] in
  [../meta/muse-spark.md](../meta/muse-spark.md#sources). [review]: gpt-oss's licence, supplied by an
  independent reviewer and not re-fetched.
- Read 2026-09-25: NVIDIA Nemotron 3 Ultra, 2026-06-04
  <https://developer.nvidia.com/blog/nvidia-nemotron-3-ultra-powers-faster-more-efficient-reasoning-for-long-running-agents/>;
  Tencent Hy4 preview, 2026-08-27 <https://huggingface.co/tencent/Hy4-preview/raw/main/README.md>;
  Xiaomi MiMo-V2.6, 2026-09-21 <https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Pro-RL/raw/main/README.md>;
  Scale SWE-Bench Pro V2, 2026-09-22 <https://labs.scale.com/leaderboard/swe_bench_pro_public_v2>;
  Artificial Analysis, open-weight launches, 2026-04-30
  <https://artificialanalysis.ai/articles/recent-open-weights-model-launches>.
