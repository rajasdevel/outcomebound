---
last_checked: 2026-09-25
volatility: MONITOR (no general LLM release since May 2026)
sources:
  - https://docs.mistral.ai/getting-started/models/models_overview/
  - https://mistral.ai/news/devstral-2-vibe-cli
  - https://docs.mistral.ai/getting-started/changelog/
  - https://raw.githubusercontent.com/mistralai/mistral-vibe/main/README.md
---

# Mistral

Mistral's current coding-agent and general models, their licences, and what is known about
prompting them. For anyone weighing a Mistral model or the Mistral Vibe CLI. Mistral sits outside
the tracked list of [../cross-family.md](../cross-family.md#scope), among "the other labs"; what
Mistral Vibe loads is in [harnesses/others.md](../../harnesses/others.md#opencode). Labels and ids
as in [../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and availability (VOLATILE)

- **Mistral Medium 3.5** (v26.04, announced 2026-05-22 with "Remote agents in Vibe") is the newest
  general-purpose LLM on the models page: "frontier-class multimodal model optimized for agentic and
  coding use cases", modified MIT [chk-mistral-models, chk-mistral-news].
- **Devstral 2** (123B, modified MIT) and **Devstral Small 2** (24B, Apache-2.0), with the Mistral
  Vibe CLI (Apache-2.0), 2025-12-09, are Mistral's last dedicated coding-agent release: 256K context,
  SWE-bench Verified 72.2% and 68.0% (lab). Devstral is absent from the current models overview
  [chk-mistral-devstral2, chk-mistral-models].
- **Mistral Large 3** is Apache-2.0 [chk-mistral-models].
- Mistral's changelog and news showed no LLM after OCR 4.1 (GA 2026-08-31, not a general LLM)
  [chk-mistral-changelog, chk-mistral-news].

## Prompting

No Mistral prompting guidance was read. Mistral Vibe reads `AGENTS.md` and `SKILL.md` skills
[chk-vibe].

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Devstral 2 (123B, modified MIT), Devstral Small 2 (24B, Apache-2.0), Mistral Vibe CLI (Apache-2.0) | 2025-12-09 | Coding-agent models, 256K context, shipped with Mistral's own open-source CLI, which reads `AGENTS.md`. SWE-bench Verified 72.2% and 68.0% (lab) | chk-mistral-devstral2, chk-vibe |
| Medium 3.5 (v26.04) | announced 2026-05-22 with "Remote agents in Vibe" | Newest general-purpose LLM on the models page: "frontier-class multimodal model optimized for agentic and coding use cases", modified MIT. No prompting guidance read; Devstral absent from the current overview | chk-mistral-models, chk-mistral-news |

## Sources

- [chk-mistral-devstral2] Mistral, Devstral 2 and Vibe CLI, 2025-12-09.
  <https://mistral.ai/news/devstral-2-vibe-cli>
- [chk-mistral-models] Mistral models overview.
  <https://docs.mistral.ai/getting-started/models/models_overview/>
- [chk-mistral-news] Mistral news index. <https://mistral.ai/news>
- [chk-mistral-changelog] Mistral docs changelog. <https://docs.mistral.ai/getting-started/changelog/>
- [chk-vibe] Mistral Vibe README.
  <https://raw.githubusercontent.com/mistralai/mistral-vibe/main/README.md>

All read 2026-09-25.
