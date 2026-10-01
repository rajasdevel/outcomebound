---
last_checked: 2026-09-25
volatility: VOLATILE (a flagship about every two months; GLM-6 reported but unconfirmed)
sources:
  - https://docs.z.ai/guides/llm/glm-5.3
  - https://z.ai/blog/glm-5.3
  - https://z.ai/blog/glm-5.2
  - https://docs.z.ai/devpack/resources/best-practice
  - https://docs.z.ai/guides/capabilities/thinking-mode
  - https://docs.z.ai/guides/capabilities/function-calling
---

# Z.ai GLM

How Z.ai's GLM models changed in how they should be prompted, from GLM-4.5 (July 2025) to the
GLM-5.3 line (September 2026), what their API requires when served by Z.ai or self-hosted, and what
is announced. For anyone running GLM in Claude Code, ZCode or a self-hosted stack, or testing shared
text on it. GLM is a tracked family in [../cross-family.md](../cross-family.md#scope); what ZCode
loads is in [harnesses/others.md](../../harnesses/others.md#zcode-zai). Labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations). The family sweep was read
2026-09-25; the GLM-5.2 blog and GLM-5.3 docs were re-read 2026-10-01 [chk-glm-blogs].

## Identity and availability (VOLATILE)

- **Flagship: GLM-5.3** (2026-08-14; API 08-18; weights 08-25 under a custom licence), the same
  base model as GLM-5.2 with every gain from post-training [glm-g9].
- **Variants that post-date it without replacing it:** GLM-5.3-Flash (08-26, MIT; a new 320B base
  with 18B active, hybrid sparse and linear attention, natively multimodal), GLM-5.3-FlashX (09-18,
  faster serving at about 200 tokens/s, prompting unchanged) and GLM-5.3-Prime (09-23, OpenRouter
  only, 1.5–2x throughput on the 5.3 weights, no Z.ai docs page) [glm-g10, glm-g11, glm-g12,
  glm-newer].
- Z.ai builds and benchmarks inside Claude Code; its own harness, ZCode, reads only a root and a
  global `AGENTS.md` [glm-g4, glm-f22].

## API surface (STABLE)

- **Thinking.** From a caller's toggle (`thinking.type`, GLM-4.5) to default-on before every
  response and tool call (4.7) to forced on (5.3): disabling thinking fails on GLM-5.3; it could be
  switched off up to 5.2 [glm-g1, glm-g3, glm-g9, glm-f15].
- **Effort.** GLM-5.2: High and Max; GLM-5.3: low, high, max, with max the default and the coding
  recommendation; effort is the only control [glm-g8, glm-g9, glm-f15].
- **Preserved thinking** requires returning `reasoning_content` unmodified; it is on by default on
  the Coding Plan endpoint and off on the standard API [glm-harness, glm-f16].
- **`tool_choice` accepts only `auto`,** so a "must call X" rule reaches the model only as prose
  [glm-f20].
- **Sampling.** Defaults temperature 1.0 and top_p 0.95: "tune one of them, not both"; GLM-5.3-Flash
  recommends temperature 1, top_p 0.95, effort max [glm-harness, glm-g10].
- **Context:** 200K from GLM-4.6, 1M from GLM-5.2 [glm-g2, glm-g8].

## Behaviour and measurements (MONITOR)

- **Long runs.** GLM-5.1 ran single autonomous runs of up to 8 hours; earlier models "plateau" or
  declare themselves done early, so Z.ai wraps 5.1 in a review/improve/continue loop [glm-g7]. GLM-5.3
  is trained to own work end to end [glm-g9]; GLM-5.3-Flash renders, inspects and revises its own
  output [glm-g10].
- **Reward hacking** appeared more in GLM-5.2 than in 5.1 during RL, so anti-hack guards were added
  [glm-f12].
- **Point release from post-training alone.** GLM-5.3 raised Terminal-Bench 3.0 from 4.6 to 28.3 on
  the same base model [lab; measured-g17].
- **Tokens per task.** GLM-5.2 used 43k tokens per task against 26k for 5.1 (Artificial Analysis,
  indep); GLM-5.3 at max used 210M against a 140M median on the index (a comparison across models,
  not release over release); Z.ai reports 5.3 at max using fewer tokens than 5.2 on its private Code
  Bench, 75K against 96K, while scoring 34.5% against 23.4% [glm-f18, glm-f17, glm-f17 detail].
- **Instruction following over turns (MTAC-IFBench, co-authored by Zhipu).** GLM-5.2's rate of
  satisfying every constraint fell from 27.6% to 2.6% by turns 9–10; constraints in the policy file
  decay less. Instruction following was generally higher under Claude Code v2.1.14 than OpenCode
  v1.1.21 across eight models: GLM-5.2's constraint satisfaction fell from 80.4% to 76.8% and its
  all-constraints rate from 12.7% to 6.7%, though OpenCode showed less multi-turn decay; in the Claude
  Code table GLM-5.2's average constraint satisfaction (80.4) was just above Opus 4.6's (78.6)
  [glm-f7, glm-f8, glm-f9, glm-f10, glm-f10 detail].
- **Harness.** Z.ai reports its best GLM-5.2 Terminal-Bench 2.1 result in Claude Code (82.7, against
  81.0 in Terminus-2) [lab; glm-f9 detail, chk-glm-blogs].
- On Scale's SWE-Bench Pro V2, GLM-5.3 scored 84.3 [measured-g22].

## Prompting (MONITOR)

- **Frame:** Goal / Context / Constraints / Done when, which Z.ai says "draws on the official
  guidance of leading tools" [glm-f1].
- **Rules in a repository file,** concrete and checkable; keep the main file under 200 lines; Z.ai
  says to put engineering standards in `CLAUDE.md` or "Agent.md" [glm-f3, glm-g8]. Instruction files
  are context, not enforcement [glm-f4].
- **Hard bounds, stated:** "Do not introduce new dependencies, do not modify API contracts, and do
  not commit changes proactively", then run build, lint and tests and report results and uncovered
  risks [glm-f11]. GLM showed out-of-scope changes and unauthorized commits [glm-f11].
- **Durable state:** rules written to files survive compaction [glm-f5]; ZCode has a `/goal` feature
  [glm-f13].
- **Skills:** put the trigger in the first ~250 characters of the description [glm-f23].
- Z.ai releases carry no advice to delete old prompt text [glm-f3].

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| GLM-4.5 / 4.5-Air | 2025-07-28 | Hybrid reasoning toggled with `thinking.type`, dynamic by default; reasons between tool calls; XML-like tool-call template; positioned for Claude Code from the start | glm-g1 |
| GLM-4.6 | 2025-09-30 | 200K context; tools during reasoning; marketed inside Claude Code, Cline, Roo Code and Kilo Code; about 15% fewer tokens (Z.ai) | glm-g2 |
| GLM-4.7 | 2025-12-22 | Thinks by default before every response and tool call; Preserved Thinking across turns; per-turn thinking toggle | glm-g3 |
| GLM-5 | 2026-02-11/12 | 744B total parameters (40B active); "agentic engineering"; internal evals aligned with Claude Code's task mix | glm-g4 |
| GLM-5-Turbo | 2026-03-15 | API-only variant optimised from training for OpenClaw tasks: tool invocation, command following, timed and persistent tasks, long-chain execution | glm-g5 |
| GLM-5V-Turbo | 2026-04-01 | First multimodal coding model, for the Claude Code and OpenClaw loop | glm-g6 |
| GLM-5.1 | 2026-04-07 | Single autonomous runs of up to 8 hours. Earlier models "plateau" or declare themselves done early, so Z.ai wraps this one in a review/improve/continue loop | glm-g7 |
| GLM-5.2 | 2026-06-16 | 1M context; effort High and Max. Better adherence to engineering standards, which Z.ai says to put in `CLAUDE.md` or "Agent.md". More reward hacking than 5.1 during RL, so anti-hack guards added. Artificial Analysis: 43k tokens per task against 26k for 5.1 [indep] | glm-g8, glm-f12, glm-f18 |
| GLM-5.3 | 2026-08-14 (API 08-18; weights 08-25, custom licence) | Same base model as 5.2; every gain from post-training. Thinking forced on; effort low/high/max, max the default and the coding recommendation. Trained to own work end to end. Fewer output tokens at max than 5.2 on Z.ai's private bench (75K against 96K) [lab] | glm-g9, glm-f17 |
| GLM-5.3-Flash | 2026-08-26 (MIT) | New 320B base (18B active), hybrid sparse and linear attention, natively multimodal. Renders, inspects and revises its own output. Temperature 1, top_p 0.95, effort max | glm-g10 |
| GLM-5.3-FlashX | 2026-09-18 | Faster serving (about 200 tokens/s); prompting unchanged | glm-g11 |
| GLM-5.3-Prime | 2026-09-23 (OpenRouter only) | 1.5–2x throughput on the 5.3 weights; no Z.ai docs page | glm-g12 |

*Direction.* A flagship about every two months, each aimed at longer autonomous work. Reasoning
went from a caller's toggle to forced on, with effort the only control [glm-trend, glm-g9]. Z.ai
builds and benchmarks inside Claude Code, while its own harness, ZCode, reads only a root and a
global `AGENTS.md` [glm-g4, glm-f22]. Its written guidance is Goal / Context / Constraints / Done
when, with concrete, checkable rules in a repository file, which it says draws on "the official
guidance of leading tools" [glm-f1, glm-f3]. For the raw API: `tool_choice` supports only `auto`;
sampling defaults are temperature 1.0 and top_p 0.95, "tune one of them, not both"; preserved
thinking requires returning `reasoning_content` unmodified [glm-harness].

## Announced, not released

| Model | Announced | Status | Source |
| --- | --- | --- | --- |
| GLM-6.0 | 2026-08-31 (results call) | Secondary reports only; minutes say next-generation base training "has already begun". Not found in the release check of 2026-10-01 | glm-next, chk-releases |

Z.ai says of GLM-5.3-Flash: "We are now scaling this recipe to larger models" [glm-next]. Forecasts
G1 (forced thinking stays), G2 (a dated GLM-6.0 page) and G3 (the Flash attention recipe reaches a
larger GLM) are scored in [../cross-family.md](../cross-family.md#8-forecasts).

## Sources

- [chk-glm-blogs] GLM-5.2 blog <https://z.ai/blog/glm-5.2> and GLM-5.3 docs
  <https://docs.z.ai/guides/llm/glm-5.3>, read 2026-10-01.
- [chk-releases] is defined in [../cross-family.md](../cross-family.md#sources).
- Z.ai, read 2026-09-25: GLM-4.5, 2025-07-28 <https://z.ai/blog/glm-4.5>; GLM-4.6, 2025-09-30
  <https://z.ai/blog/glm-4.6>; GLM-4.7, 2025-12-22 <https://z.ai/blog/glm-4.7>; GLM-5, 2026-02
  <https://docs.z.ai/guides/llm/glm-5>; GLM-5-Turbo, 2026-03 <https://docs.z.ai/guides/llm/glm-5-turbo>;
  GLM-5V-Turbo, 2026-04 <https://docs.z.ai/guides/vlm/glm-5v-turbo>; GLM-5.1, 2026-04-07
  <https://z.ai/blog/glm-5.1>, <https://docs.z.ai/guides/llm/glm-5.1>; GLM-5.2, 2026-06-16
  <https://docs.z.ai/guides/llm/glm-5.2>; GLM-5.3, 2026-08-14 <https://z.ai/blog/glm-5.3>;
  GLM-5.3-Flash, 2026-08-26 <https://z.ai/blog/glm-5.3-flash>,
  <https://docs.z.ai/guides/vlm/glm-5.3-flash>; undated: best practice
  <https://docs.z.ai/devpack/resources/best-practice>, memory mechanism
  <https://docs.z.ai/devpack/resources/memory-mechanism>, thinking mode
  <https://docs.z.ai/guides/capabilities/thinking-mode>, function calling
  <https://docs.z.ai/guides/capabilities/function-calling>.
- Secondary: Simon Willison on GLM-5.2, 2026-06-17 <https://simonwillison.net/2026/jun/17/glm-52/>;
  OpenRouter models API (read 2026-09-25) <https://openrouter.ai/api/v1/models>; Artificial Analysis
  model page <https://artificialanalysis.ai/models/glm-5-3> (read 2026-09-25).
- MTAC-IFBench (co-authored by Zhipu), 2026-09-14, re-read 2026-10-01
  <https://arxiv.org/abs/2609.14992>.
