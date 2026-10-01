---
last_checked: 2026-10-01
volatility: STABLE (the studies change only with new research) / MONITOR (the legal timelines in §5, which moved twice in a year)
sources:
  - https://arxiv.org/abs/2502.00977
  - https://arxiv.org/abs/2502.20258
  - https://arxiv.org/abs/2310.00785
  - https://arxiv.org/abs/2407.15021
  - https://arxiv.org/abs/2404.16130
  - https://arxiv.org/abs/2401.18059
  - https://arxiv.org/abs/2410.01736
  - https://arxiv.org/abs/2505.24575
  - https://arxiv.org/abs/2506.16411
  - https://arxiv.org/abs/2510.05154
  - https://arxiv.org/abs/2509.15723
  - https://arxiv.org/abs/2509.06902
  - https://arxiv.org/abs/2305.14627
  - https://arxiv.org/abs/2407.20371
---

# Summaries, summary layers and citations

Re-check when a study measures drift level by level in a summary hierarchy, compares small with
frontier models on short summarization inputs, or measures citation accuracy on current models; the
legal section before any rollout that summarizes records about people.

What summaries of summaries lose, which summary shapes and layers hold up, how numbers and minority
views fare in generated summaries, and how far a model's citations can be trusted. For anyone who
designs a precomputed summary or memo layer over a corpus, a handoff built from earlier handoffs, or
a report that cites its sources. How a long context degrades and what compaction keeps are in
[long-context-and-compaction.md](long-context-and-compaction.md); what agents remember between
sessions is in [agent-memory.md](agent-memory.md).

**Evidence classes**, as in [the index](../README.md): M measured; L lab or vendor documentation or
guidance; S standard or protocol specification; P practitioner consensus; A anecdote or one
uncontrolled report; F forecast; O own result. Papers are cited by arXiv id and were read on
2026-10-01; a number taken from a paper's body rather than its abstract is marked "body". Most
studies tested models of 2023–2025.

## Key findings

**CM5. Summaries of summaries lose faithfulness; going back to the source and adding structure
recover it.** Hierarchical merging scored below one-pass summarizing on faithfulness, and putting
source passages back at each merge restored it; repeated regeneration drifts from the source; keyed
JSON summaries beat prose by about 40% F1. M.

**CM6. A model's citations are claims.** Even the best models of 2023 lacked complete citation
support about half the time on long-form answers. Check that each cited file or source says what it
is cited for. M.

## 1. Summaries and summarization layers

- **Faithfulness falls with each merge.** On long legal documents (about 156,000 input tokens on
  average), plain hierarchical merging scored 72.9 on AlignScore against 79.3 for summarizing in one
  pass, and replacing each level's summaries with retrieved source passages scored 84.6
  (Llama-3.1-8B, Multi-LexSum, body). On Llama-3.1-70B the gap between merging and one pass was
  small on Multi-LexSum (76.3 against 77.6), and citation-based merging scored best there (85.8); on
  the SuperSummary narrative set the 70B model's citation-based replacing scored 78.4 against 57.8 for
  plain merging, about 20.6 points (body). The replacing variant lost coverage, and people judged
  27.3% of claims in merged summaries incorrect against 20.0% for one pass [arXiv 2502.00977, Ou and
  Lapata, ACL Findings 2025]. M. No published study gives a level-by-level drift curve for a
  hierarchy deeper than this.
- **Repetition drifts.** In chains of up to 100 translation or rephrasing rounds by 7–9B models,
  "distortion accumulates over time"; lower temperature and restrictive prompts reduced it but did
  not stop it [arXiv 2502.20258, ACL 2025]. M.
- **Running summaries.** Book summaries built by updating one running summary were less coherent
  than hierarchically merged ones but more detailed, and the models "consistently" added to the
  running summary instead of removing from it, so a separate prompt had to condense it [arXiv
  2310.00785, BooookScore, ICLR 2024]. M. Because a running summary is built in order, removing one
  earlier fact means rebuilding it from that point on, where summaries of separate time partitions
  can be rebuilt one partition at a time (inference; the paper does not test it).
- **Structure helps.** Keyed JSON intermediate summaries scored about 40% higher F1 than prose ones
  on SUMIE and 14% higher on a book set by its coherence metric, and updating the keys incrementally
  added 7% and 4% more (Gemini models) [arXiv 2407.15021]. M. Keys are also what let one slot be
  replaced, cited or checked on its own (inference).
- **Precomputed summary layers.** GraphRAG's root-level community summaries answered questions about
  a whole corpus with 26,657 tokens a query, against 1,014,611 for map-reduce over the source text
  (2.6%); they won 72% of comparisons on comprehensiveness against vector retrieval, but not against
  the source-text map-reduce, and the global methods as a group won 72–83% [arXiv 2404.16130]. The
  asset that transfers is the summary layer, not the graph (inference). RAPTOR found that one pool
  holding every level beat walking the tree, with 18.5–57% of retrieved nodes coming from summary
  levels [arXiv 2401.18059]: summaries speed retrieval while the source stays reachable. Its
  clustering needs near-full recomputation when documents are added or removed [arXiv 2410.01736].
  M.
- **Chunk size for map-reduce.** In NexusSum's ablation, 300-word chunks gave the best BERTScore F1
  on BookSum (67.16), MovieSum (62.78) and MENSA (65.43), against 50.51, 55.49 and 55.25 at the
  maximum 100K chunk (body) [arXiv 2505.24575, ACL 2025]. A noise-decomposition study of
  divide-and-conquer over long contexts found that "even with three to five samples per
  configuration, the selected chunk sizes are near-optimal and often *exactly* match the
  exhaustive-search optimum" (body, §5.5) [arXiv 2506.16411]. M. Small fan-in per call holds up
  even as windows grow; the long-context evidence is in
  [long-context-and-compaction.md](long-context-and-compaction.md).
- **Minority views.** Across 18 models, summaries of many opinions represented minority positions
  less well than majority ones [arXiv 2510.05154]. Asking the model to first count how many inputs
  hold each view improved proportional representation on larger models; an 8B model skipped the
  counting step [arXiv 2509.15723, REFER]. M.
- **Names and bias.** In an audit of text embedding models used to retrieve resumes for nine
  occupations (over 500 resumes and 500 job descriptions), the models favoured White-associated
  names in 85.1% of cases and female-associated names in only 11.1%, and Black male names were
  disadvantaged in up to 100% of cases [arXiv 2407.20371, Wilson and Caliskan]. M (retrieval
  models, not generative summarizers). Whether prompt instructions or removing names reduce such
  bias in a summary layer was not measured there (`UNVERIFIED`).
- **For handoffs.** A handoff written from an earlier handoff is a summary of a summary; it goes back
  to the sources it cites (inference from the above; the handoff evidence is W2 in
  [agent-workspace.md](agent-workspace.md)).

## 2. Numbers in generated text

- **Verify numbers outside the model.** Proof-Carrying Numbers proposes that the model wrap each
  number in a tag pointing to a structured claim and that the renderer, not the model, verify it and
  show any untagged number as unverified; the paper gives proofs and no measured result [arXiv
  2509.06902]. A design, not a measurement.
- **Counts can be given to the model.** Supplying the frequency of each view before summarizing is
  what improved minority coverage in §1 (REFER), on larger models.
- No measured rate was found for how often a model complies with an instruction to leave numbers
  out of a summary (`UNVERIFIED`); a renderer-side check is the only control with a guarantee.

## 3. Citations

- On long-form answers to ELI5 questions, "even the best models lack complete citation support 50%
  of the time" (the ChatGPT and GPT-4 baselines of 2023, citation recall about 50); reranking samples
  raised ChatGPT's citation recall to 69.3 (body) [arXiv 2305.14627, ALCE, EMNLP 2023]. M.
- GitHub Copilot's memory stores repository facts with citations to the code, and checks those
  citations against the current branch when it uses them [harness-loading-coverage-16]. L.
- A citation is therefore a claim: check that each cited file, line or source says what it is cited
  for, and drop or mark a citation the check cannot support. Where a lineage record exists (which
  inputs fed which summary), it is the ground truth, and a model's self-citation is not (inference).
  No study found measures citation accuracy on current coding agents.

## 4. What is not established

- No level-by-level drift curve for a summary hierarchy deeper than two or three merges.
- No literature on log-structured summarization (daily summaries rolled into weekly and yearly
  ones); the pattern is an analogy with time-series aggregates, not an established NLP method.
- No head-to-head of small against frontier models on very short summarization inputs (tens of
  tokens each); a tier decision there needs its own evaluation.
- No measured compliance rate for "omit numbers" instructions (§2).

## 5. Summaries about people: legal timelines (MONITOR)

A summary layer over records about employees or applicants sits near regulated territory. Read
2026-10-01 through law-firm and press summaries of each act; not legal advice. S.

- **EU AI Act.** Annex III point 4 covers AI systems used in employment, including to monitor and
  evaluate the performance and behaviour of workers; under Article 6(3) an Annex III system that
  profiles natural persons is always high-risk. The Digital Omnibus on AI, Regulation (EU)
  2026/1744, published 2026-07-24 and in force 2026-07-27, defers the high-risk obligations for
  stand-alone Annex III systems to 2027-12-02 (Annex I products to 2028-08-02).
- **New York City Local Law 144.** Applies to automated employment decision tools, tools that
  substantially assist or replace discretionary hiring or promotion decisions and produce a
  simplified output such as a score, classification or recommendation; it requires an annual
  independent bias audit, a public summary and advance notice; enforced since 2023-07-05.
- **Illinois HB 3773.** In force 2026-01-01: amends the Illinois Human Rights Act to prohibit AI use
  in employment decisions that has the effect of discrimination on a protected class, whatever the
  intent, and requires notice to employees; the Department of Human Rights sets the notice rules.
- **Colorado.** SB 26-189 repeals and replaces SB 24-205, narrows it to transparency and rights
  around consequential automated decisions, drops the duty of reasonable care, risk-management
  programmes and annual impact assessments, and takes effect 2027-01-01.

## How to apply

1. Treat summaries of summaries, and handoffs built from handoffs, as lossy: go back to the sources at
   each merge, and prefer keyed structure to prose (§1).
2. Keep raw sources reachable beside any summary layer, in one retrieval pool, and partition
   summaries by time or entity so that a deleted source forces a local rebuild, not a replay (§1).
3. Keep each call's fan-in small; pick the chunk size from a few sampled documents (§1).
4. Verify every number in generated text against its source in code, not by instruction (§2).
5. Check every citation a model gives against what it cites (§3).
6. Before summarizing records about people, check the jurisdictions that apply (§5).

## Limits and open questions

- Most studies tested models of 2023–2025, at 7B to 70B for the open models; whether frontier models
  of late 2026 drift the same way is open.
- The legal section was read through secondary summaries, not the statutes' text.
- §4 lists what no source establishes.

## Sources

Papers (arXiv, read 2026-10-01, each at `https://arxiv.org/abs/<id>`): 2502.00977 (Ou and Lapata,
context-aware hierarchical merging; tables read in the HTML version), 2502.20258 (broken telephone),
2310.00785 (BooookScore), 2407.15021 (structured incremental summaries), 2404.16130 (GraphRAG),
2401.18059 (RAPTOR), 2410.01736 (adRAP), 2505.24575 (NexusSum, appendix D), 2506.16411 (when divide
and conquer works for long context, §5.5), 2510.05154 (DeliberationBank), 2509.15723 (REFER),
2509.06902 (Proof-Carrying Numbers), 2305.14627 (ALCE), 2407.20371 (Wilson and Caliskan, resume
screening via retrieval).

Evidence record: [harness-loading-coverage-16].

Legal (read 2026-10-01): Hunton, EU Digital Omnibus on AI enters into force
<https://www.hunton.com/privacy-and-cybersecurity-law-blog/eu-digital-omnibus-on-ai-enters-into-force>;
Lewis Silkin, the Digital Omnibus on AI enters into force today, 2026-07-27
<https://www.lewissilkin.com/insights/2026/07/27/the-digital-omnibus-on-ai-enters-into-force-today-102nedo>;
Gibson Dunn, EU AI Act Omnibus agreement
<https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/>;
New York State Comptroller, enforcement of Local Law 144
<https://www.osc.ny.gov/state-agencies/audits/2025/12/02/enforcement-local-law-144-automated-employment-decision-tools>;
Hunton, Illinois enacts new law regulating employer use of AI
<https://www.hunton.com/hunton-employment-labor-perspectives/illinois-enacts-new-law-regulating-employer-use-of-artificial-intelligence>;
McDermott, Colorado AI bill signed after predecessor's enforcement blocked
<https://www.mcdermottlaw.com/insights/colorado-ai-law-in-flux-comprehensive-replacement-bill-signed-after-federal-court-blocks-predecessors-enforcement/>;
Eckert Seamans, Colorado repeals and replaces its landmark AI statute
<https://www.eckertseamans.com/legal-updates/colorado-repeals-and-replaces-its-landmark-ai-statute-what-businesses-need-to-know>.
