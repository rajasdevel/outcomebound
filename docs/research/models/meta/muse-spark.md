---
last_checked: 2026-09-25
volatility: MONITOR (open weights "on the roadmap"; no agent-prompting guide found)
sources:
  - https://research.meta.ai/blog/introducing-muse-spark-1-3
  - https://dev.meta.ai/docs/muse-code/configuration.md
---

# Meta Muse Spark

What Meta's Muse Spark models are and what Meta says about their agent behaviour. For anyone
weighing Muse Spark or Muse Code. Meta sits outside the tracked list of
[../cross-family.md](../cross-family.md#scope) as its own comparison group; the research recommends
tracking it. Verified from a primary source; labels and ids as in
[../cross-family.md](../cross-family.md#evidence-labels-and-citations).

## Identity and behaviour (VOLATILE)

- **Muse Spark 1.3** (2026-09-02): closed weights, open weights "on the roadmap". Ships in Muse Code,
  Meta's coding agent, and the Meta Model API [chk-meta].
- It "asks clarifying questions when prompts are ambiguous, invokes help from the user when stuck,
  and confirms before taking consequential actions" [lab; chk-meta].
- About 25% fewer tokens and 20% fewer tool calls than 1.2 (Meta's comparison) [lab; chk-meta].
- No Muse Spark agent-prompting guide was found, and Muse Code's instruction-file loader was not
  verified [chk-meta]; Muse Code's configuration page is in
  [harnesses/others.md](../../harnesses/others.md#windsurf-devin-desktop).

## Lineage (VOLATILE)

| Model | Released | What changed for prompting | Ids |
| --- | --- | --- | --- |
| Muse Spark 1.1 | date not verified | Topped Scale's SWE-Bench Pro public v1 board, per the research | measured-newer |
| Muse Spark 1.2 | date not verified | Ranked by Artificial Analysis and The Register | gemini-newer |
| Muse Spark 1.3 | 2026-09-02 | Closed weights; open weights "on the roadmap". Ships in Muse Code, Meta's coding agent, and the Meta Model API. "Asks clarifying questions when prompts are ambiguous, invokes help from the user when stuck, and confirms before taking consequential actions." About 25% fewer tokens and 20% fewer tool calls than 1.2 (Meta's comparison) [lab] | chk-meta |

*Direction.* Meta trains Muse Spark to ask, escalate and confirm before consequential actions, and
reports falling token and tool-call use [lab]. Muse Code's instruction-file loader was not verified
[chk-meta].

## Announced, not released

| Model | Announced | Status | Source |
| --- | --- | --- | --- |
| Muse Spark open weights | 2026-09-02 | "On the roadmap" | chk-meta |

Forecast M1 (Meta releases open weights for a Muse Spark model by 2027-03-31) is scored in
[../cross-family.md](../cross-family.md#8-forecasts).

## Sources

- [chk-meta] Meta, Introducing Muse Spark 1.3, 2026-09-02, read 2026-09-25.
  <https://research.meta.ai/blog/introducing-muse-spark-1-3>
- Muse Code configuration (undated, live 2026-09-25) <https://dev.meta.ai/docs/muse-code/configuration.md>.
