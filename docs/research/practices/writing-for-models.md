---
last_checked: 2026-09-25
volatility: MONITOR (the practices change at a model generation) / VOLATILE (the harness caps and listing limits in S7, S10 and §7.4) / STABLE (the audit method §7–§8 and the measurement arithmetic §9)
sources:
  - https://arxiv.org/abs/2602.11988
  - https://arxiv.org/abs/2602.12670
  - https://arxiv.org/abs/2505.13360
  - https://arxiv.org/abs/2505.06120
  - https://arxiv.org/abs/2605.07769
  - https://arxiv.org/abs/2605.10039
  - https://arxiv.org/abs/2507.11538
  - https://arxiv.org/html/2607.27250
  - https://arxiv.org/html/2509.22040v1
  - https://genai.owasp.org/download/52117/?tmstv=1765059207
  - https://code.claude.com/docs/en/skills
  - https://code.claude.com/docs/en/memory
  - https://claude.dev/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models/
  - https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra.md
  - https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
---

# Writing for models: instruction files, skills, briefs and tool output

Re-check when a tracked lab or harness ships a model, a prompting guide or a change to what it
loads, or a practice reverses at a model release.

This reference answers what the evidence supports about writing the text a coding agent's model
reads: always-loaded instruction files (`AGENTS.md`, `CLAUDE.md` and their equivalents) and
blocks installed into them, skills, delegation briefs, and the output of the tools and checks the
agent runs. It grades each practice (S1–S19) by evidence class and by the reader tiers its evidence
covers, says what is contested, what belongs in deterministic code rather than prose, how to audit
a project's instruction files safely (hidden characters, concealed content, override phrases,
risky harness settings), how to revise text sentence by sentence, and how to measure a change to
model-facing text. It closes with a per-rule reading of the evidence behind a writing standard
built from these practices (SR1–SR22). It is for anyone who writes, reviews or audits such text,
and for a project checking its own instruction files. What each harness loads is in
[harnesses.md](../harnesses/cross-harness.md); how the models changed is in [models.md](../models/cross-family.md); skills in
depth are in [skills.md](skills.md).

## Key findings

1. **State the outcome, the completion bar, the constraints and when to stop, up front; leave the
   path to the reader unless the path is itself a requirement.** Models infer unspecified
   requirements 41.1% of the time; requirements revealed over several turns cost 39%; framing "no
   change" as a valid outcome raised correct abstention from 65.0% to 80.5% (Sonnet 4.6) and 60.5%
   to 88.5% (GPT-5.4 mini), while a prescribed reproduce-first step caused wrong abstentions.
   Measured (S1) [research-18, research-14, research-28].
2. **Rules that must hold without exception belong in the harness, not in prose.** Instruction
   files are advisory; compliance with one convention fell about 5.6% per function written in
   Claude Code sessions; process non-compliance was invisible in transcripts; reliable following
   breaks down beyond five or six simultaneous constraints on one output. Measured and lab-guidance
   (S2) [research-3, research-29, measured-f2, harness-loading-coverage-9].
3. **Instruction files, skills, memory and the harness configuration beside them are untrusted
   supply-chain input.** Planted rule files hijacked agents in up to 84% of attacks on Cursor and
   52% on Copilot; 84.2% of skill vulnerabilities sat in `SKILL.md`; hooks, `.mcp.json` and endpoint
   overrides were exploited as CVEs; adaptive attacks bypassed 12 of 12 recent published defenses.
   Measured,
   standards and anecdote (S4) [instruction-file-security-authority-30,
   instruction-file-security-authority-15, instruction-file-security-authority-17,
   instruction-file-security-authority-27].
4. **Text that disagrees with the code it names does more harm than no text.** Agents follow a
   stated standard even when it is wrong, and a missing fact produces fabricated work; check
   agreement before judging anything else. Measured (S14) [repo-readiness-audits-25].
5. **"Done" is a check the agent can run that returns pass or fail, and reports say what was not
   verified.** A gate on the agent's own verdict accepted everything, and 56% of the cycles it
   claimed as improvements had zero or negative measured effect; auditing each claim against a tool
   result "nearly eliminated fabricated status reports" on Fable 5. Measured (S5)
   [deterministic-28, forward-15].
6. **Always-loaded text should hold only what its readers would get wrong without it.** Every line
   is obeyed (a named tool was used 1.6 times per task against under 0.01 when unnamed); context
   files did not generally raise success and raised cost by more than 20%; self-evident constraints
   degraded coding. Counter-evidence exists, and one study finds long, detailed contexts better for
   evolving playbooks. Measured, on frontier, mid and small readers (S8) [research-4, research-5,
   research-17, research-27].
7. **Reader tiers want different text, and most deletion evidence comes from frontier readers.**
   Small models drop instructions silently as they accumulate; a file written by a strong model did
   not help a small reader; guidance tuned on one small model dropped another to 13.2%. Measured
   that tiers differ; how one shared file serves several tiers is untested (S3)
   [capability-tier-readers-17, capability-tier-readers-20, agent-files-8].
8. **State each rule once, in one vocabulary, with no contradictions across the layers that load
   together.** Contradictions, retired settings and scratchpads cost Opus 5 7 to 11 accuracy
   points; stacked conflicts fail silently and GPT-5-mini collapses hardest. Measured (S9)
   [capability-tier-readers-10, capability-tier-readers-21].
9. **Compact, curated skills beat comprehensive documentation; self-generated skills do harm.**
   Curated skills added 16.6 points on average (compact +19.0, standard +21.5, comprehensive +0.7);
   self-generated skills scored 8.1–11.5 points below no skill. Measured (S10) [research-8,
   research-9].
10. **Tool and check output should be designed for an agent reader:** silence or one line on
    success, only the failures with reason and fix, bounded, non-interactive, with meaningful exit
    codes. Structured interfaces made repeated attempts up to 4.7x more consistent; input length
    alone degraded performance 13.9–85%. Measured and standards (S6) [deterministic-29,
    research-12, other-labs-23].
11. **Absolutes and emphasis over-trigger on newer models; keep them for true invariants.** Lab
    guidance, contested by one measurement on 2025 models (S17) [anthropic-4, forward-10,
    research-15].
12. **A before/after of model-facing text at five runs a side catches only large drops.** A real
    20-point drop reads as equal or better 26–33% of the time; only drops of about 40–60 points are
    caught reliably; rewordings moved tool-calling results 11–58x more than reruns did. Computed and
    measured [evals-21, research-19].
13. **An audit of instruction files must treat the files as hostile to the auditor.** A
    deterministic security pass runs before any model reads them, nothing from the project is
    executed (even a working-tree `git diff` can run a project's clean filter), and a model's
    verdict alone resolves to `UNVERIFIED`. Lab-guidance and measured
    [instruction-file-security-authority-19, instruction-file-security-authority-26,
    instruction-file-security-authority-28].
14. **Revising text to a standard yields agreement repairs more than cuts, and a rewrite can change
    meaning its own coverage record calls carried.** In OutcomeBound's audit of 1,090 sentences,
    agreement repairs (24) outnumbered cuts (11); in a rewrite of the same text, six of eight
    fresh-context reviews found changes of meaning the rewrite's record called carried. Review each
    rewrite against the before text. Own observation (§8).

## 1. Scope, method and evidence

### Scope and window

- **Practice** (§2–§3): which ways of writing instruction files, skills, fragments, briefs and tool
  output are best supported, how strongly, for which readers, and which way each is moving.
- **Open questions** (§4): where the evidence conflicts or is missing, and what would settle it.
- **Support and measurement** (§5–§9): what belongs in deterministic code; how tool output should
  read; how to audit a project's instruction files; how to revise text; how to measure a change.
- **A standard's evidence, rule by rule** (§10).
- **Window.** Mostly January 2025 to 25 September 2026, plus a few older studies (Lost in the
  Middle, 2023; Anthropic's statistical approach to evals, 2024). The per-rule review (§10) was read
  on 2026-09-27.

### How the research was done

1. **Topic sweeps.** Readers worked in parallel, one per topic, reading primary sources where they
   could be reached, and recorded each finding with its claim, a verbatim quote, the URL, the
   publication date, the source type, an evidence class and a stance. The sweeps, by id prefix: lab
   guidance (`anthropic-`, `openai-`, `other-labs-`), research papers (`research-`), practitioners
   (`practitioners-`), aggregator coverage (`latent-space-`), instruction files (`agent-files-`),
   deterministic support (`deterministic-`), evals (`evals-`) and direction of travel (`forward-`).
2. **Completeness critique and gap sweeps.** A critic read the first synthesis for what it had
   missed and named four gaps, each then swept: reader tiers (`capability-tier-readers-`), harness
   loading (`harness-loading-coverage-`), the security and authority of instruction files
   (`instruction-file-security-authority-`), and readiness audits and linters
   (`repo-readiness-audits-`).
3. **Model-family sweeps**, run alongside (`claude-`, `openai-g`/`openai-f`, `grok-`, `glm-`,
   `qwen-`, `gemini-`, `open-weight-`, and cross-family measurement `measured-`); this reference
   cites them where one bears on a practice.
4. **Fact-check.** A separate pass re-read every source against its record and gave one of three
   verdicts: supported; overstated, with the claim corrected; or dropped. Of the 733 sweep records
   with a verdict, 566 were supported, 167 overstated and none dropped; the checked
   `advanced-tool-use` record, supported, makes 734, and the 32 family summary notes carry no
   verdict. A rewritten record keeps its first wording in `original_claim`, and, where the
   correction changed the class, the first class in `original_evidence`; this reference uses the
   corrected claim and class throughout.
5. **Synthesis and adversarial critique.** The practices were synthesised, critiqued by an
   independent reviewer and revised. The critic raised one source with no evidence record,
   Anthropic's "Introducing advanced tool use" (2025-11-24); it was fetched and checked on
   2026-09-25 and is cited as [advanced-tool-use].
6. **Final re-checks** on 2026-09-25 of two facts no evidence record quoted: Claude Code's
   skill-description cap and its 4 MiB `CLAUDE.md` skip [chk-claude-skills, chk-claude-memory].
7. **Second reading** on 2026-10-01. Specifics kept in the records' `detail`, and OutcomeBound's own
   observations, were re-read at their sources before entering this reference; where a source said
   otherwise than the note, the text follows the source, and a figure no source carries is dropped.

### Evidence classes

| Mark | Class | Meaning |
| --- | --- | --- |
| (M) | measured | a measured effect; where the models measured matter, the text names them |
| (L) | lab-guidance | guidance or a documented fact from a lab or tool vendor |
| (S) | standard | a standards body: OWASP, the OpenAI Model Spec, `AGENTS.md`, Agent Skills, NIST |
| (P) | practitioner-consensus | several practitioners converging |
| (A) | anecdote | an anecdote or one person's opinion |
| (F) | forecast | a statement about the future |
| (O) | OutcomeBound's own record | OutcomeBound's eval runs and audit records, scoped as stated |

A measured record is further marked *independent* of the model's maker, *lab-own-model* (a lab
measuring its own model) or *vendor-own-product* where that matters. `UNVERIFIED` marks what the
evidence does not establish.

### Reader tiers

Where a practice deletes text, it names the reader tier its evidence covers [anthropic-10,
capability-tier-readers-9]. A family's top tier is **frontier** (Opus, Fable and Mythos; the GPT
flagships, GPT-4o in its day and GPT-6 Astra; Gemini Pro; the Grok, GLM, Qwen and MiniMax
flagships); its middle tier is **mid** (Sonnet; GPT-6 Sol; Gemini Flash); its smallest tier, and an
open model of about 35B parameters or fewer, is **small** (Haiku; the GPT mini and nano models and
GPT-6 Luna; Flash-Lite; Qwen3-30B, Qwen3-32B, Qwen3.5-35B-A3B, Qwen2.5 7B, Nemotron Nano). A source
that names no reader is read as written for the top tier of its day, and no coverage below it is
claimed without a named model.

### Citations

- `[prefix-N]` (a topic record), `[family-gN]` (a model release), `[family-fN]` (a family finding)
  and `[family-trend|next|harness|newer]` (a family note) resolve by `id` in
  [`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl), which holds every record the sweeps
  produced (765) and the checked `advanced-tool-use` record. Each carries its claim as verified, a
  verbatim quote, the URL, the date (`published`, or `released`), a `verification` of supported or
  overstated, and, on topic records and findings, its class (`evidence`). A range such as
  `[latent-space-1 to latent-space-6]` cites every id in it.
- **The evidence file's fields.** One JSON object per line, keyed by a unique `id`, of four kinds:
  `practice` (421 topic records, `advanced-tool-use` among them), `finding` (197 family findings),
  `generation` (116 model releases and cross-family studies) and `family-note` (32 family
  summaries). Fields: `claim`, as verified; `original_claim`, the first wording, where the
  fact-check rewrote the record (where it confirmed the claim and `claim` holds its note,
  `original_claim` is the finding as the sweep stated it); `detail`, the sweep reader's note beside
  the claim, kept as read and not itself fact-checked; `verification` (`supported` or
  `overstated`) on every record but a family note; `quote` and `url`; `published`, or `released`
  and `model` on a generation record; on topic records and findings, `evidence` (`measured`,
  `lab-guidance`, `practitioner-consensus` or `anecdote`), the class the verified claim supports,
  `stance` and `source`; on topic records also `type` (the source's kind) and `by`; and
  `original_evidence`, the first class, where a correction changed it. A family note carries only
  `id`, `kind`, `family` and `claim`.
- `[chk-…]` and `[advanced-tool-use]` are facts checked at their source, listed under Sources.
- A few specifics are marked "record detail" or "sweep detail": they come from the `detail` a
  sweep reader recorded beside a record's claim, which the evidence file keeps but the fact-check
  did not verify. Treat them as the reader's notes on that source. Where such a specific was
  re-read at its source on 2026-10-01, the text says so and gives that reading.
- [`_evidence/2026-09-25-sources.json`](../_evidence/2026-09-25-sources.json) lists the 583 sources
  the 2026-09-25 sweeps read and the 64 pages that were unreachable or read only in part, each with
  what was read instead. A source in it that no record cites was read and yielded no finding.
- S1–S19 are the practices of §2; D1a, D1b and D2–D21 (deterministic), X1–X3 (execution) and
  J0–J12 (judgment) the audit checks of §7; SR1–SR22 the per-rule review of §10; R-, "Do" and
  "Stop" ids are in [models.md](../models/cross-family.md).

### Limits of the evidence

- **Reached second-hand or in part.** OpenAI's harness-engineering post returned 403 and was read
  from a verbatim mirror and through a browser [agent-files-23, forward-25]. Grove's talk transcript
  and OpenAI's post retiring SWE-bench Verified could not be reached; both are covered through
  Latent Space [latent-space-27, evals-30]. The Weng quote reached the research through AINews
  [latent-space-17]; her post was also read directly [practitioners-1]. Two Latent Space issues
  were read only as far as the paywall [repo-readiness-audits-27, repo-readiness-audits-30]. The
  Z.ai, Qwen Code and DeepSeek pages were reached by direct URL only, not through search; this
  reference relies on them for ZCode's skill caps (S10) and for the Qwen findings §5 cites.
- **How much was read.** The sweeps' source list (§1, Citations) records 64 pages unreachable or
  read only in part: pages that returned HTTP 403 and were read through a browser or a verbatim
  mirror; paywalled pages; guides published only as PDFs, among them Anthropic's complete guide to
  building skills; PDFs that could not be decoded, so that McMillan's factorial study [research-3]
  and Wharton's first prompting report were read from their abstracts; seven arXiv papers read by
  abstract only in one sweep (2607.25152, 2608.11386, 2602.11988, 2607.27250, 2606.20512,
  2604.07236, 2608.13867); the ETH study of 138 agent files and GitHub's analysis of more than 2,500
  `agents.md` files, read second-hand; METR's basic-scaffold result, Scale SWE-Atlas and
  Harness-Bench, known only as others cite them; and pages not reached at all (Codex and Copilot
  compaction, Koi Security's ClawHavoc report, OpenAI's "Understanding prompt injections", Cisco's
  skill-scanner docs). The figures this
  reference takes from 2602.11988, 2607.27250 and 2608.11386 were re-read in their full text on
  2026-10-01 (Sources).
- **Weak designs.** Several measured results are single-author preprints [research-3,
  research-15, research-29, capability-tier-readers-26]; others are vendor reports [research-11,
  other-labs-29]. Readiness scorers publish no validation against agent outcomes
  [repo-readiness-audits-4, repo-readiness-audits-6, repo-readiness-audits-11]. Several security
  cases are single-incident reports [instruction-file-security-authority-6,
  instruction-file-security-authority-7, instruction-file-security-authority-17].
- **The current frontier is barely tested.** No public study runs one `AGENTS.md` across current
  models from several families [measured-f16], and the compliance studies test only models released
  before the newest flagships (§4.2).
- **Tiers.** Most deletion evidence comes from frontier readers; no study tests how one shared file
  serves several tiers at once.

## 2. The practices (S1–S19)

### 2.1 How the practices are ranked

1. **Merge findings that trace to one primary source.** A relay counts only toward the source it
   relays. Each cluster counts once: OpenAI's harness-engineering work, the post and Lopopolo's
   Latent Space interview [openai-20, openai-21, agent-files-23, agent-files-24, forward-25,
   deterministic-1, deterministic-3, deterministic-4, deterministic-5, latent-space-1 to
   latent-space-6, practitioners-24, forward-26, repo-readiness-audits-28,
   repo-readiness-audits-29]; the ETH `AGENTS.md` study [research-4, research-5, agent-files-1,
   agent-files-2, other-labs-28, deterministic-30, forward-28, practitioners-7,
   capability-tier-readers-19, capability-tier-readers-20, repo-readiness-audits-24]; Vercel
   [other-labs-29, agent-files-6, evals-22]; the Claude 5 context-engineering post and its relays
   of the "80% deleted" claim [forward-1 to forward-4, agent-files-14 to agent-files-16; relays
   latent-space-14, practitioners-3, agent-files-28, forward-23, deterministic-25]; SkillsBench
   [research-8, research-9, agent-files-7]; IFScale [research-1, capability-tier-readers-17,
   capability-tier-readers-18]; the GPT-6 Astra blog post [openai-10 to openai-15, agent-files-21,
   agent-files-22, capability-tier-readers-1, capability-tier-readers-2]; Anthropic's "Demystifying
   evals" [evals-1 to evals-9, evals-14, anthropic-28, deterministic-14, forward-30]; Weng
   [practitioners-1, practitioners-30, latent-space-17, deterministic-26, deterministic-27]; the
   lethal-trifecta post [practitioners-19, instruction-file-security-authority-23].
2. **Group what remains by organisation or individual.** A lab counts once however many posts it
   published. Agent Skills began at Anthropic and is counted with Anthropic. Each research team
   counts once. Eugene Yan and Addy Osmani are Anthropic staff writing personally, so they count as
   practitioners. Philipp Schmid, of Google DeepMind's developer relations, writing on his own blog
   likewise counts as a practitioner, not as Google [other-labs-12 to other-labs-17]; "Google"
   names only Google's own pages.
3. **Bucket and order.** Practices are bucketed by the number of independent groups behind them: at
   least 10, 7–9, 4–6, or 3 and fewer. Within a bucket, the strongest evidence comes first: a
   measured effect on agent outcomes, then on something narrower, then a documented fact, then
   guidance.
4. **A caveat on counts.** S7's count reflects each vendor documenting its own harness. It shows
   how widespread a fact is, not agreement on a recommendation.

Severity in an audit follows a different order, set by harm and evidence (§7.8).

### 2.2 Bucket A: ten or more independent groups

**S1. State the outcome, the completion bar, the constraints and when to stop.** The completion bar
is a runnable check or an observable result, plus the shape of the output. Leave the path to the
model unless the path is itself a requirement; readers below the frontier may still need one (the
tier caveat below, and S3).
- **Why it works.**
  - Underspecification makes models guess: by default they infer unspecified requirements 41.1% of
    the time, and underspecified prompts are twice as likely to regress across model or prompt
    changes; listing every requirement does not consistently help, while requirements-aware prompt
    optimisation improved performance by 4.8% on average [research-18] (M). Much of the variance
    blamed on wording comes from underspecification: on three text-classification tasks and six
    models, underspecified prompts varied more and specific instruction prompts less (Pecher et
    al., arXiv 2602.04297, read 2026-10-01) (M).
  - Requirements revealed over several turns cut performance by 39%, regardless of model aptitude;
    small models are also more sensitive to harmless rewording [research-14,
    capability-tier-readers-28] (M, 2025 models). Setting both temperatures to 0 left unreliability
    near 30%; restating the requirements recovered part of the loss (the "snowball" form 15–20%)
    but still lagged a single complete instruction [research-14; re-read 2026-10-01] (M, GPT-4o
    and 4o-mini). A later study finds that drift over turns settles at a bounded level rather than
    growing, and that restating the goal at set turns reliably reduces it (Dongre et al., arXiv
    2510.07777, read 2026-10-01) (M).
  - Agents proposed undesirable changes in 35–65% of cases where no change was right, on 200
    human-verified tasks whose issue was already fixed, five models across four harnesses. Framing
    the outcome as "abstain or fix" raised correct abstention from 65.0% to 80.5% on Sonnet 4.6 and
    from 60.5% to 88.5% on GPT-5.4 mini, with resolution on SWE-bench Verified staying within the
    confidence intervals; an "edit" framing cut GPT-5.4 mini's correct abstention to 36.5%. A bare
    reproduce-first prompt did not help (Sonnet 4.6 65.0% to 65.5%) and made the small reader worse
    (60.5% to 47.5%); instructions to reproduce and then abstain partly addressed the problem but
    caused wrong abstention on partly fixed issues [research-28; re-read 2026-10-01] (M).
  - On GPT-5.5, legacy prompts that over-specify the process "can add noise, narrow the model's
    search space, or lead to overly mechanical answers", so start from a fresh baseline [openai-2,
    forward-8] (L). A planner that fixes technical details up front risks cascading its errors
    downstream; constrain the deliverables and let the agent find the path (a design concern in
    one experimental harness, not a measurement) [anthropic-7] (L).
  - "Minimal does not mean short": aim for the smallest set of information that fully specifies
    the expected behaviour [anthropic-2] (L).
- **OutcomeBound's result (O).** Stating the required form of a decision brief inline in a skill
  moved gpt-6-sol from 0 of 3 to 3 of 3 runs on a scenario whose deciding fact was in reach. The gain
  was in the answer's form; the checking done before asking showed no gain, since runs without the
  text still read the files that settled the decision. Limits: 3 runs per arm; judged by a model of
  the same family; the prompts carried a "no questions" line; in the earlier of its runs the workspace
  directory name exposed the scenario.
- **Tier caveat.** OpenAI makes "do not prescribe every step" depend on the model's capability, not
  a universal rule [capability-tier-readers-6] (L, GPT-5.6 family). Readers below the frontier still
  gain from explicit plans [capability-tier-readers-22] (M), [capability-tier-readers-26] (M, weak).
- **Groups (13).** Anthropic [anthropic-7, anthropic-26, forward-17]; OpenAI [openai-1, openai-13,
  openai-23, openai-28, forward-7]; Google [other-labs-3]; Schmid [other-labs-14, other-labs-17];
  Z.ai [capability-tier-readers-30]; CMU (Yang, Kästner) [research-18]; Microsoft/Salesforce
  [research-14]; ETH SRI [research-28]; Eugene Yan [practitioners-14]; Karpathy [practitioners-26];
  Amp [latent-space-13]; Weng [practitioners-1]; Hylak [latent-space-24].
- **Confidence: high.** Three measured studies, plus the one-project result on output form. No study
  compares an outcome-first instruction file with a procedural one for coding agents.
- **Trend: rising.** OpenAI moved from GPT-5's context-gathering recipes to outcome, constraints and
  stop rules [openai-1].

**S2. Enforce in the harness any rule that must hold without exception, through permissions,
hooks, a sandbox, CI, linters or structured outputs. Keep prose for judgment.**
- **Why it works.**
  - Instruction files are advisory context: Claude "treats them as context, not enforced
    configuration. To block an action regardless of what Claude decides, use a PreToolUse hook"
    [agent-files-12] (L). Prompted rules fail under pressure, in long sessions and under injection;
    "a real guardrail needs to be deterministic" [anthropic-16] (L). In one harness, hooks, not the
    instruction file, guarantee an action that must happen every time [deterministic-9] (L). Claude
    Code's auto-mode classifier does not store boundaries stated in conversation as rules; it
    re-reads them from the transcript on each check, so compaction can drop them, and a deny rule is
    the hard guarantee [deterministic-10] (L).
  - LLMs "are unable to reliably distinguish the importance of instructions based on where they
    came from", so prose defenses against injected instructions are unreliable [practitioners-19]
    (P).
  - The odds of complying with one convention fell about 5.6% per additional function written (OR
    0.944, found after the fact and not monotonic), in one factorial study of one harness: 1,650
    Claude Code sessions (16,050 function-level observations) on two TypeScript codebases and five
    tasks, mainly Sonnet 4.6 with Opus 4.6 as a check and Opus 4.7 reported descriptively, the
    compliance target a trivial per-function annotation; file layout showed no detectable effect,
    with the size and conflict nulls supported by Bayes factors of 0.05–0.10 [research-3; the
    abstract, which carries these counts, re-read 2026-10-01; the full text was not read] (M,
    Claude Code).
  - Compliance with process instructions was 0% under default framing, and raters could not detect
    the non-compliance from the transcript (nine blinded raters, Fleiss' κ 0.130); removing the
    delegation tools raised compliance to 75%. Across 13 experiments and 2,031 sessions on six
    frontier models, compliance was 97% where following the process was rewarded in the task
    (audit trails) and 0–4% where it was not, and Claude Sonnet 4 agreed to the instruction in 10 of
    10 runs and bypassed it in all 10 [research-29; re-read 2026-10-01] (M, single author,
    directional).
  - Reliable instruction following breaks down beyond five or six simultaneous constraints on one
    output, so check them with deterministic verifiers [measured-f2] (M).
  - Anthropic describes its auto-mode classifier as deliberately conservative, tuned to overeager
    initiative [deterministic-11] (L). The same post measures it: on 52 real overeager actions,
    curated from sessions where an employee denied the action or it was flagged afterwards, the
    full pipeline missed 17% ("the honest number"), against 0.4% false positives on 10,000 actions
    of real traffic and 5.7% misses on 1,000 synthetic exfiltration attempts; the post says it "is
    not a drop-in replacement for careful human review on high-stakes infrastructure"
    [deterministic-11 detail; post re-read 2026-10-01] (M, lab-own-product).
  - Filesystem plus network isolation cut Anthropic's internal permission prompts by 84%
    [deterministic-12] (M).
  - Deterministic defenses give guarantees; probabilistic ones only reduce likelihood
    [instruction-file-security-authority-22] (L).
  - Hooks and loop monitors are among the adaptations that helped small models
    [capability-tier-readers-23] (M).
- **Groups (14).** Anthropic [anthropic-16, anthropic-17, deterministic-8 to deterministic-12];
  OpenAI [openai-21, openai-25]; Cursor [agent-files-27, harness-loading-coverage-9]; HumanLayer
  [practitioners-9]; Factory [deterministic-19]; Stripe [deterministic-18]; Willison
  [practitioners-19]; Microsoft [instruction-file-security-authority-22]; Meta
  [instruction-file-security-authority-24]; McMillan [research-3]; Shin [research-29]; CMU
  (Kästner) [capability-tier-readers-23]; Beurer-Kellner et al.
  [instruction-file-security-authority-21]; Gray Swan [instruction-file-security-authority-29].
- **Confidence: high.**
- **Trend: rising.** Capable models "route around restrictions nobody thought to write down"
  [anthropic-17].

**S3. Know which readers load each surface, helpers and subagents included, and test the text on
each tier it has to serve. Keep any one model's quirks out of portable text.**
- **Tiers want different text.** "Guidance that helps Sol or Luna may overconstrain GPT-6 Astra"
  [openai-15, capability-tier-readers-1] (L, unmeasured). All of OpenAI's GPT-6 prompting guidance
  comes from Astra [capability-tier-readers-3] (L). Anthropic publishes no Haiku 4.5 guide
  [capability-tier-readers-9] (L).
- **Measured differences between tiers.**
  - Small models decay exponentially as instructions accumulate, and drop instructions silently
    rather than approximating them [capability-tier-readers-17, capability-tier-readers-18] (M,
    2025 models).
  - Context files written by GPT-5.2 or Sonnet 4.5 and read by GPT-5.1 mini or Qwen3-30B moved
    results by +2% on SWE-bench and −3% on CTXbench [capability-tier-readers-20] (M).
  - Guidance tuned on one small open-weight model dropped another to 13.2% [agent-files-8] (M).
  - An LLM "prompt compiler" that clusters, merges and adds precedence notes recovered +11.0 points
    for GPT-5-mini, +3.3 for Gemini 2.5 Flash and nothing for Sonnet 4.6 [capability-tier-readers-21]
    (M, three models).
  - Task-specific harnesses improved 16 of 21 small-model pairs (3B–8B active parameters), the
    best small agent recovering 89.7% of the large model's performance at 4% of the cost; frontier
    models do well with general ones [capability-tier-readers-22; re-read 2026-10-01] (M).
  - Structured prompting still helps some 7B models, unevenly: across three runs Qwen2.5 7B gained
    +4.4 to +8.0% over zero-shot from contrastive chain of thought and −1.3 to +7.2% from few-shot
    examples, while GPT-4o's gains shrank (19,620 generations on 218 Python functions; Qwen2,
    Qwen2.5 7B and Mistral-7B among six models) [capability-tier-readers-27; re-read 2026-10-01]
    (M, older models).
  - Format and placement effects are model-specific and cannot be predicted in advance
    [capability-tier-readers-25] (M).
  - A strong critic's concrete fixes raise a small agent's success (Qwen3-32B under Opus 4.6:
    40.6% against 26.8% with high-level critiques), largely by copying; when the critic offered
    several candidate fixes, the agent picked the wrong one. A small critic should steer a large
    agent at a high level [capability-tier-readers-15, capability-tier-readers-16] (M): 4B and 8B
    critics significantly lifted all six larger agents on SWE-Bench Verified (GPT-OSS-120B from
    20.4 to 34.8, GLM-4.7-Flash from 21.6 to 37.6), and a critic trained on high-level critiques
    beat one trained on detailed ones (13.8% against 12.6% on Qwen3-32B)
    [capability-tier-readers-15; re-read 2026-10-01]. The paper
    says nothing about outcome-only guidance, so "concrete steps for a weaker reader" means
    task-specific fixes, not a generic read-check-verify sequence.
- **Literal readers.** Sonnet 5 needs the scope of an instruction stated explicitly
  [capability-tier-readers-7, anthropic-5] (L), and follows filter phrases literally, which lowers
  recall [capability-tier-readers-8] (L).
- **Quirks run in opposite directions** [anthropic-10] (L): "Where a technique names a specific
  model, treat it as measured on that model and re-check it against your own evals before applying
  it to another." Anthropic now restricts each model-specific system-prompt change to the model it
  targets [anthropic-9] (L). A harness tuned for one model scored lower on Opus 4.6
  [deterministic-22] (M). A skill meant for several harnesses "cannot assume they all provide
  identical capabilities" [latent-space-29] (A).
- **Who loads nothing.** Claude Code's built-in Explore and Plan subagents, Kiro custom agents and
  untrusted Codex projects never load the surface [capability-tier-readers-13,
  harness-loading-coverage-23, harness-loading-coverage-19]. Where a harness or helper loads a
  skill without the instruction file, and no pointer can make that file load, the skill has to
  carry the minimal restatement its reader needs; elsewhere each rule is stated once (reasoning,
  effect unmeasured).
- **Consequence.** Each deletion practice below (S8, S11, S16) holds only for the tiers its
  evidence covers, and each names them. The evidence shows that tiers differ, not which tier a
  shared text should be written for.
- **Groups (14).** Anthropic; OpenAI; Shepard & Albrecht; ETH SRI; CMU (Kästner); CMU (Gandhi,
  Rosé); Rudyk et al.; MHIL; Anand & Chattaraj; Distyl; LangChain; Qwen [capability-tier-readers-29];
  Bakaus [latent-space-29]; Khan (weak).
- **Confidence.** High that tiers differ; medium on how one shared file can serve both.
- **Trend: rising.** Labs now name the mismatch between tiers [capability-tier-readers-1].

**S4. Treat instruction files, skills, memory and the harness configuration beside them as
untrusted supply-chain input.** Scan them before a model reads them, pin third-party ones, review
changes like code, and load project instructions only in trusted workspaces.
- **Coding agents follow planted instructions.**
  - Infected rule files hijacked coding agents even when the user's request never mentioned the
    files: with 314 payloads covering 70 MITRE ATT&CK techniques planted in rule files, attack
    success reached 66.9–84.1% across five scenarios on Cursor's auto mode and at most 52.2% on
    GitHub Copilot, and on Cursor it held across five phrasings of the request (17–19 of 20
    attacks) [instruction-file-security-authority-30; re-read 2026-10-01] (M). The payloads can
    serve as fixtures for an audit's detection classes.
  - Payloads already in memory files attacked current and future sessions; stronger models were
    less likely to change existing instructions, so upgrading the model does not remove a planted
    payload, and changes to high-impact instruction files need review
    [instruction-file-security-authority-12] (M).
  - In a study of 98,380 skills, 84.2% of vulnerabilities sat in `SKILL.md`, and 73.2% of malicious
    skills carried undocumented features; coercive language, secrecy directives and autonomy
    overrides mark malicious skills, and a capability the skill does not document is the strongest
    sign [instruction-file-security-authority-15] (M).
  - Of 3,984 skills scanned on ClawHub and skills.sh, 36.82% had at least one security flaw and
    13.4% a critical one; 2.9% of the ClawHub skills, and 21% of known-malicious samples, fetched
    and executed remote content at run time [instruction-file-security-authority-14; re-read
    2026-10-01] (M, vendor scan).
  - Microsoft found more than 50 memory-poisoning prompts that use "remember" and "trusted source"
    [instruction-file-security-authority-13] (M).
- **Concealment.** Since 2025-05-01 github.com shows a warning when a file's contents include
  hidden Unicode text, after a 2021 warning for bidirectional text (L, GitHub changelog, read
  2026-10-01); Cursor's answer to the rules-file backdoor, as the researchers' disclosure timeline
  summarises it, was that the risk "falls under the users' responsibility"
  [instruction-file-security-authority-6 detail; re-read 2026-10-01] (A). Neither is a detector to
  rely on: hidden Unicode moved to variation selectors, which passed GitHub's web UI and VS Code
  with no visible sign [instruction-file-security-authority-7] (A). A homoglyph slipped past
  review [instruction-file-security-authority-8] (A). Some models can read Tag characters as
  instructions [instruction-file-security-authority-9, instruction-file-security-authority-10]
  (A/P).
- **Configuration is executable too.** Hooks, `.mcp.json` and base-URL overrides in
  `.claude/settings.json` were exploited as CVEs [instruction-file-security-authority-17] (A). The
  keys that execute or widen permissions in each harness are listed in
  [harnesses.md](../harnesses/cross-harness.md#94-configuration-keys-that-execute-code-or-widen-permissions) §9.4.
- **Defenses written in prose fail.** Adaptive attacks bypassed 12 of 12 recent defenses
  [instruction-file-security-authority-27] (M). In a competition of 272,000 attack attempts from
  464 participants against 13 models, 8,648 succeeded while hiding the compromise from the final
  reply, from 0.5% of attempts on Claude Opus 4.5 to 8.5% on Gemini 2.5 Pro and 2.51% in coding
  scenarios; universal attack strategies transferred across 21 of 41 behaviours, and capability
  and robustness were only weakly correlated (r = −0.31, not significant)
  [instruction-file-security-authority-26; re-read 2026-10-01] (M). System-prompt reminders are not
  a defense [instruction-file-security-authority-29] (P). A defense has to be evaluated against
  adaptive, newly red-teamed attacks with repeated attempts per task, not a fixed attack set: new
  red-team attacks raised attack success from 11% to 81%, and 25 attempts a task raised average
  success from 57% to 80% [instruction-file-security-authority-25; re-read 2026-10-01] (M, NIST
  CAISI). A later CAISI evaluation found agents built on DeepSeek R1-0528 on average 12 times as
  likely as the US frontier models it evaluated to follow malicious instructions (NIST, 2025-09-30,
  read 2026-10-01) (M), so the model used in any audit step is itself a security parameter.
- **Standards.** OWASP classes these risks as ASI01 (goal hijack), ASI04 (supply chain) and ASI06
  (memory and context poisoning), and recommends hash pinning and scanning memory writes
  [instruction-file-security-authority-1, instruction-file-security-authority-3,
  instruction-file-security-authority-4] (S).
- **Versioned like configuration.** Context files "evolve like configuration code"
  [agent-files-4] (M), and OpenAI lints its knowledge base in CI [agent-files-24] (A). In the same
  study's 2,303 context files from 1,925 repositories (Claude Code, Codex, Copilot), build and run
  commands, implementation detail and architecture dominate (62.3%, 69.9% and 67.7% in its first
  version; 63.0%, 70.8% and 68.1% in its second, which also counts testing at 75.9%), and security
  and performance appear in about 15% each; how often content appears was measured, not its effect
  [agent-files-4 detail; v1 2025-11-17 and v2 2026-08-09 read 2026-10-01] (M). Google's
  threat intelligence team advises limiting which agent-facing files (`AGENTS.md`, `SKILL.md`,
  agent settings, hooks) a repository may contain, requiring automated review before merge, and
  giving agents least-privilege access [other-labs-11] (L). The same team reports a consistent
  increase since the start of 2026 in `SKILL.md` files submitted to VirusTotal with risky or
  malicious instructions (not all of them harmful), among them a skill telling the model to
  exfiltrate API keys, tokens and configuration files under the guise of maintenance and not to
  mention it, and `settings.json` files that override `ANTHROPIC_BASE_URL`, embed an API key and
  make Claude Code the client of a third-party proxy [other-labs-11 detail; post re-read
  2026-10-01] (L). Meta's Muse Code docs treat
  repository-committed memory as a prompt-injection surface [other-labs-27] (L). Anthropic runs a
  broad per-model eval suite for every change to Claude Code's system prompt [anthropic-9] (L), and
  a practitioner advises a targeted eval for each instruction change that asks "did only this
  change", the full suite before merge, and per-eval failure budgets [evals-26] (P).
- **Material brought into a brief.** Anthropic and xAI advise marking quoted or pasted material as
  data, not instructions [claude-g13, grok-f7] (L); its effect is `UNVERIFIED`.
- **Groups (24).** OWASP; Google Threat Intelligence [other-labs-11]; Pillar; Aikido; Stenberg;
  Rehberger; CSA; Invariant Labs; Gadgil et al.; Microsoft; Snyk; Liu et al.; Check Point;
  Anthropic [instruction-file-security-authority-18, instruction-file-security-authority-19];
  OpenAI [instruction-file-security-authority-20]; Beurer-Kellner et al.; Willison; Meta
  [instruction-file-security-authority-24, other-labs-27]; NIST CAISI; the Gray Swan/AISI
  competition; Nasr, Carlini, Tramèr et al.; Zhao et al.; the AIShellJack authors; GitHub
  [harness-loading-coverage-14].
- **Confidence: high.**
- **Trend: rising.** Daily skill submissions went from under 50 to over 500
  [instruction-file-security-authority-14].

**S5. Make "done" a check the agent can run that returns pass or fail. Require reports grounded in
evidence, with anything unverified said to be unverified.**
- **Why it works.**
  - Without a check, "looks done" is the only signal the agent has [anthropic-20] (L).
  - A gate built on the agent's own verdict accepted everything, and 56% of the cycles it claimed
    as improvements had zero or negative measured effect; an externally grounded gate closed the gap
    [deterministic-28] (M).
  - Auditing each claim against a tool result "nearly eliminated fabricated status reports"
    [anthropic-21, forward-15] (M, Fable 5, the lab's own testing).
  - A separate, skeptical judge is easier to make reliable than self-critique [anthropic-23] (L).
  - The smallest current model fits high-volume work whose output can be checked, not long agentic
    loops [capability-tier-readers-11] (M, Haiku 4.5 against Opus 5.5, the lab's own measurement).
- **What a "Done" line needs.** It names the command that actually settles completion, runnable as
  written: a scoped fast check is not the test suite; a check that only observes is not a
  completion bar; a command template holding a placeholder (`--base <branch>`) is not runnable
  verbatim; and a command soft-wrapped across Markdown lines cannot be extracted reliably by a
  reader that parses lines (reasoning; observed in OutcomeBound's composed fragments, §7.4).
- **Groups (11).** Anthropic; OpenAI [openai-24]; Google [other-labs-6]; `AGENTS.md`
  [other-labs-18]; Hashimoto [practitioners-13]; Yan [practitioners-15]; Willison [practitioners-17,
  deterministic-21]; Weng [practitioners-30]; Cursor [latent-space-23]; Park & Choi
  [deterministic-28]; Exadel [repo-readiness-audits-16].
- **Confidence: high.**
- **Trend.** Stable for runnable checks; rising for evidence-grounded reports.

**S6. Design every tool, script and check output for an agent reader.** On success, print one line
or nothing. On failure, print only the failures, each with its reason and fix on the same line.
Bound the length, never prompt interactively, offer structured output on request, use meaningful
exit codes, and assume no one harness's conventions (detail in §6).
- **Why it works.**
  - The shape of an interface changes behaviour even at equal capability: structured interfaces
    made repeated attempts up to 4.7x more consistent, and CodeAct-style tools matched task
    performance in 41.6% fewer steps and with 56.3% fewer tokens; natural-language search raised
    access to relevant files by more than 11% but added noise (11,700 trajectories over six tool
    architectures holding the same information) [deterministic-29; re-read 2026-10-01] (M).
  - Input length alone degraded performance by 13.9–85%, even with perfect retrieval [research-12]
    (M). Distractors compound the loss [research-11] (M, vendor report).
  - Error messages that carry the fix act as "positive prompt injection" [deterministic-2,
    latent-space-2] (L/A).
  - Harnesses truncate output [other-labs-23, deterministic-13] (L): at roughly 10–30K characters
    in the Agent Skills guidance, and Claude Code caps tool responses at 25,000 tokens by default
    (both from the sweep's record detail).
  - How well models follow tool-call formats varies widely across scaffolds
    [capability-tier-readers-29] (M).
- **Counterpoint.** Hiding output can make what the agent sees diverge from what happened
  [latent-space-5] (A); folding rather than dropping answers it (§6).
- **Groups (10).** Anthropic [anthropic-27, deterministic-13]; OpenAI [deterministic-5]; HumanLayer
  [practitioners-10]; Poehnelt [deterministic-20]; Böckeler [deterministic-2]; Xu et al.; Du et al.;
  Chroma; Mistral [other-labs-26]; Notion [latent-space-9].
- **Confidence: high.**
- **Trend: rising.**

**S7. Know how each target harness loads, truncates, ranks and compacts every instruction layer:
project, user, local, managed-policy and memory files. Place each text where it survives.** The
per-harness facts are in [harnesses.md](../harnesses/cross-harness.md); the caps an audit checks are D1a, D1b and D2
(§7.4).
- **What matters most.** Put what must load in the root `AGENTS.md` and what must survive
  compaction in the root file, unscoped rules and the top of each `SKILL.md`
  [harness-loading-coverage-7, harness-loading-coverage-8] (L); stay under the tightest enforced
  caps, 24,000 bytes per file and 32 KiB for the whole chain [harness-loading-coverage-19,
  harness-loading-coverage-21] (L).
- **Moved text counts only where it is still reached.** Text moved out of the always-loaded file
  into an on-demand file is carried only where the harness's loading facts show that file loads, or
  a post-check shows it was read when its condition held; text moved to a file the reader's install
  does not carry is deleted for that reader (reasoning resting on [agent-files-5, other-labs-29]).
- **Installed text is model-facing text.** Preambles, routing lines and pointer blocks an installer
  writes into `AGENTS.md`, and the messages of the checks it installs, are read every session like
  hand-written text and need the same standard (reasoning).
- **Groups (16).** Anthropic, OpenAI, Google, Cursor, GitHub, Microsoft (VS Code), Cognition
  (Windsurf/Devin), AWS (Kiro), JetBrains (Junie), Cline, Qwen, OpenHands, OpenCode, xAI, Meta and
  `AGENTS.md` [harness-loading-coverage-11 to harness-loading-coverage-28, other-labs-7,
  other-labs-25].
- **Confidence: high as facts.** The facts drift: Copilot removed its review cap on 2026-06-12
  [harness-loading-coverage-13].
- **Trend: rising.** Harnesses converged on the `AGENTS.md` name but not on budgets or precedence.

### 2.3 Bucket B: seven to nine groups

**S8. Put in always-loaded text only what its readers would get wrong without it.** That means
non-standard conventions, commands they cannot guess, gotchas and invariants. Leave out overviews
and anything a reader can derive from the repository.
- **Why it works.**
  - Files are obeyed: a tool named in the file was used 1.6 times per task, against fewer than 0.01
    when it was not named, so every line has an effect [research-4] (M).
  - Context files did not generally raise success, and raised cost by more than 20%; files
    generated by a model changed success by −0.5% on SWE-bench and −2% on CTXbench, lowering it in
    5 of 8 settings and adding 2.45 and 3.92 steps per task, while developer-written files changed
    it by +2.4% on average (p = 0.21); repository overviews did not help [research-4, research-5]
    (M). The readers were Claude Code on Sonnet 4.5, Codex on GPT-5.2 and GPT-5.1 mini, and Qwen
    Code on Qwen3-30B-coder, so the evidence includes small readers; the repositories were Python
    only. The same study finds context files useful for non-standard practices and advises
    evaluating any change against a no-file baseline, including its token cost, before it ships
    [evals-23].
  - With the repository's own documentation removed, generated files did help (+2.7% on average),
    so a generated context file mostly duplicates the documentation beside it; file length and
    dropping categories of instruction showed no significant effect [agent-files-1, measured-f7;
    the study re-read in full 2026-10-01, v2 and v3] (M).
  - Do not commit model-generated (`/init`-style) context files without task-grounded evaluation:
    they add cost without improving success, files generated by stronger models were not
    consistently better (+2% on SWE-bench, −3% on CTXbench), and the generation prompt made little
    difference [agent-files-2] (M); "Don't use /init or let the agent write its own AGENTS.md"
    [other-labs-13] (M, one practitioner's reading of the data).
  - Adding self-evident constraints degraded task-solving: several models kept under 60% of their
    coding performance [research-17] (M, including Sonnet 4.5).
  - Knowledge absent from training can gain a lot: a compressed 8 KB index of version-specific
    Next.js docs in `AGENTS.md` took pass rates from 53% to 100% [other-labs-29] (M, vendor, N not
    reported).
- **Counter-evidence.** One study found `AGENTS.md` presence associated with 28.64% lower median
  runtime and 16.58% fewer output tokens at comparable completion, across 10 repositories and 124
  pull requests, with one agent, Codex CLI on gpt-5.2-codex [research-6; re-read 2026-10-01] (M, an
  association). A two-agent ablation (July 2026; 288 evaluated runs of Claude Code on Sonnet 4.6 and
  Codex on GPT-5.5 over 17 tasks from three Python repositories, each with no file, an always-on
  file and a selective wiki, three repeats) found no measurable effect on correctness, bounding it
  below 10 points for Claude Code and 15 for Codex, and traced the failures to implementation skill
  rather than missing repository knowledge [evals-23, evals-19 details; the study behind evals-18
  and evals-19, re-read 2026-10-01] (M). A third argues against brevity itself: models "are more
  effective when provided with long, detailed contexts", and iterative rewriting toward brevity
  erodes detail (brevity bias, context collapse) [research-27] (M, 2025 models; evolving agent
  playbooks rather than instruction files). In its example a rewrite cut an 18,282-token context
  scoring 66.7 to 122 tokens scoring 57.1, below the 63.7 of no adaptation at all; incremental
  updates instead gained +10.6% on agent tasks (AppWorld) and +8.6% on finance [research-27; re-read
  2026-10-01]. Which content goes into the file decides the result [other-labs-28, research-7].
- **Tiers.** The labs' deletion guidance is written for frontier readers [anthropic-14] (L, models
  unstated).
- **Groups (9).** Anthropic [anthropic-14, agent-files-11, agent-files-13, agent-files-15]; OpenAI
  [openai-27]; Schmid [other-labs-12]; Cursor [agent-files-27]; Meta [other-labs-27]; HumanLayer
  [practitioners-6]; ETH SRI; Tsinghua [research-17]; Vercel.
- **Confidence.** High on the direction; medium on the size of the effect.
- **Trend: rising** for frontier readers.

**S9. State each rule once, in one vocabulary, with no contradictions across any layer that loads.
Say which source wins when instructions could collide.**
- **Why it works.**
  - On Opus 5, contradictions, retired settings and scratchpads together cost 7 to 11 accuracy
    points [capability-tier-readers-10] (M).
  - Pairwise conflicts between stacked instructions fail silently, and GPT-5-mini collapses the
    hardest [capability-tier-readers-21] (M): the follow rate fell from about 96% at one
    instruction to as low as 20% at twenty, and at twenty stacked instructions on GSM8K GPT-5-mini
    followed 0.206 of them against 0.591 for Sonnet 4.6, with "output JSON" the main conflict hub
    [capability-tier-readers-21; re-read 2026-10-01].
  - Given two contradictory rules, Claude "may pick one arbitrarily" [anthropic-15] (L). Anthropic
    advises reviewing the system prompt, `CLAUDE.md` and skills together for conflicting directives,
    and deleted many constraints it once needed [agent-files-14, claude-f8] (L). In transcripts of
    its own use of Claude Code it found its system prompt, skills and users' requests clashing, as
    "leave documentation as appropriate" against "DO NOT add comments", which the model then has to
    reconcile; its new system prompt says instead to write code that "reads like the surrounding
    code: match its comment density, naming, and idiom" [agent-files-14 detail; post re-read
    2026-10-01] (L).
  - Contradictory or vague prompts are more damaging to GPT-5, which spends reasoning tokens
    reconciling them; OpenAI reports early users whose GPT-5 performance was "drastically
    streamlined and improved" by removing contradictions (an anecdotal report) [openai-6] (L).
  - Conflicting skill guidance makes Astra pause [openai-8, forward-27] (L).
  - Repeating "ask first" causes needless stops [capability-tier-readers-5] (L, GPT-5.6 family).
  - Repetition with rising severity is debt tied to one model [practitioners-4] (P). Anthropic
    itself retired "repeat yourself" for Claude 5 models in favour of simple tool descriptions:
    earlier models "could sometimes need repeated instructions or be more likely to listen to
    instructions at the end of their context window" [agent-files-14 detail; post re-read
    2026-10-01] (L).
  - Different names for one thing confuse agents [latent-space-28] (A).
- **Against.** No detectable adherence effect from a contradicting instruction in an adjacent file,
  in one harness, on a trivial annotation (Sonnet 4.6, Opus 4.6 and 4.7) [research-3] (M). The
  measured benefit is on weaker readers; the one measured null is on strong readers in one harness.
  OutcomeBound's probed diagnostic points the same way: a skill that contradicted its own reference
  file stopped gpt-6-luna in two of three runs and gpt-6-sol in none (S14) (O, three runs a cell).
- **Groups (9).** Anthropic; OpenAI [openai-6, forward-5]; Mistral [other-labs-26]; GitHub
  [agent-files-26]; Breunig; Yan [practitioners-16]; Pocock; Anand & Chattaraj; Microsoft (VS Code)
  [harness-loading-coverage-10, harness-loading-coverage-11].
- **Confidence: high.** It is now measured.
- **Trend: rising.**

**S10. Keep skills compact, curated by a person and single-purpose.** Write each description as the
condition that triggers the skill, with the key use case first and within every listing cap.
Detail in [skills.md](skills.md).
- **Why it works.**
  - Curated skills raised the average pass rate from 33.9% to 50.5% (+16.6 points) over 87 tasks
    with deterministic verifiers and 18 model–harness configurations, with per-configuration gains
    of +4.1 to +25.7. By length, compact (+19.0) and standard (+21.5) skills beat detailed ones
    (+14.5) and comprehensive documentation (+0.7, a bin of five tasks); focused skills of at most
    three modules beat larger bundles (four or more, +10.1). Thirteen of the 87 tasks got worse
    with skills, and software engineering (+11.6) and mathematics (+9.7) gained least [research-8;
    v4 re-read 2026-10-01] (M).
  - Self-generated skills scored 8.1–11.5 points below having no skill at all, on Opus 4.7, GPT-5.5
    and Gemini 3.1 Pro, where curated skills added 18.2–24.8 points on the same configurations; the
    self-generated skills were written with Anthropic's skill-creator [research-9; re-read
    2026-10-01] (M).
  - How a skill is organised changes behaviour far more than outcomes: rewriting only its
    organisation (progressive disclosure) on 82 tasks raised the distinct resources touched per
    trajectory from 1.18 to 3.85 and skill-uptake events from 1.33 to 3.92, for 17 more passing
    trials of 410 (+4.1%, inside a paired interval of ±6.0) [research-10; re-read 2026-10-01] (M).
  - Descriptions are truncated: Claude Code cuts a skill's combined `description` and `when_to_use`
    at 1,536 characters in the model-facing listing [chk-claude-skills], and its `/skills` menu
    shows 250 [claude-harness]; Codex shortens descriptions to fit 2% of context or 8,000
    characters [openai-14, openai-harness]; ZCode injects the first 250 characters and drops a
    skill whose description exceeds 1,024 [glm-f23, glm-harness] (L).
  - The description is a trigger condition, not a summary for people [agent-files-17] (L). Missing
    trigger guidance is the most common skill defect, though its link to retrieval is only
    observational: trigger-complete descriptions scored higher in a lexical retrieval test, and no
    description was repaired and re-measured [agent-files-10] (M).
  - Constraints written in a skill's file were the least-followed category for every model tested,
    closed ones included (Opus 4.5 58%, Sonnet 4.5 52%) [open-weight-f7] (M, January 2026 models;
    benchmark co-authored by MiniMax).
  - Two fixes, rewriting one skill's description to match the user's intent rather than the API's
    terms and replacing passive deprecation warnings with explicit instructions, took it from 66.7%
    to 100% over about 20 test cases; the description change alone fixed 5 of 7 failures
    [other-labs-15; re-read 2026-10-01] (A, one practitioner's measurement).
- **Groups (9).** The SkillsBench team; the SkillJuror team; Zhang et al.; Hong et al.
  [agent-files-9]; Anthropic [anthropic-12, anthropic-18]; OpenAI [openai-15,
  capability-tier-readers-2]; Schmid [other-labs-14, other-labs-15]; Pocock [other-labs-30]; Bakaus.
- **Confidence.** High for compact and curated; medium for the description rules.
- **Trend: rising.**

**S11. Prune one group of lines at a time, and re-run the same evals at each model generation.** Ask
of each line whether removing it would cause a mistake, and answer for each tier that loads it: most
of the deletion evidence is from frontier readers. The sentence test in §8 is one way to do it.
- **Why it works, and on which tier.**
  - Anthropic deleted over 80% of Claude Code's system prompt with "no measurable loss"
    [forward-1] (M, internal; Claude 5 frontier: Opus 5 and Fable 5).
  - Leaner prompts, cut one group at a time and re-run on the same evals, scored higher at lower
    cost [forward-5] (M, GPT-5.6 family, tier unstated, "directional").
  - An audit on the move from Sonnet 4.6 to Sonnet 5 cut cost by 14% at the same accuracy
    [capability-tier-readers-10] (M, mid tier; not measured on Haiku 4.5).
  - Upgrades that raise aggregate scores still reliably regress up to 8.3% of items, and strict
    instruction following regressed on the latest migration [measured-g18] (M, GPT-5.4 → 5.5 → Sol).
  - One added length line ("≤25 words / ≤100 words") passed weeks of testing on a narrower eval set;
    broader ablations then showed a 3% drop on one evaluation for Opus 4.6 and 4.7 [anthropic-9] (M).
  - Decay as instructions accumulate starts early: at 6–10 instructions [research-2]. Reasoning
    models such as o3 and gemini-2.5-pro stay near-perfect through 100–250 instructions, then fall
    to about 63–68% at 500; the best frontier model reached 68% at 500 [research-1] (M, 2025
    models).
  - Skills and prompts written for earlier models are "often too prescriptive" for newer ones:
    review them on migration and consider removing older instructions where default behaviour is
    better [anthropic-6, forward-13] (L, Fable 5).
  - At 80 rules, perfect-response rates reached zero on every model tested; about 40 simultaneous
    instructions is the point to redesign [capability-tier-readers-24] (M; Sonnet 5, Haiku 4.5,
    Gemini 3.5 Flash, Qwen 27B/35B).
  - Radical cuts hid which parts carried the load [anthropic-8] (L): "every component in a harness
    encodes an assumption about what the model can't do on its own, and those assumptions are worth
    stress testing", one component at a time, at each new model [deterministic-15] (L).
  - Against: repeated rewriting toward brevity erodes the details that carried the load (context
    collapse) [research-27] (M, 2025 models).
- **Counter-evidence for small readers** [capability-tier-readers-22, capability-tier-readers-27]
  (M).
- **Groups (8).** Anthropic; OpenAI [openai-5, agent-files-21]; Schmid [other-labs-16,
  other-labs-17]; Distyl; Harada et al.; MHIL; LangChain [deterministic-22]; Vercel
  [deterministic-23].
- **Confidence.** High for the method; medium for any deletion on small readers.
- **Trend: rising strongly** for frontier readers.

**S12. Keep the always-loaded file a short map.** Point to skills and references with a condition
("read X when Y"), one level deep. Knowledge needed on most tasks stays inline as a compact index.
- **Why it works.** Pointers tied to conditions beat "read A, B, C before every edit" [openai-11]
  (L). Progressive disclosure saves attention [forward-4, openai-20] (L/A).
- **Measured qualifiers.**
  - The skill was never invoked in 56% of cases, while the inline index scored 100%
    [other-labs-29] (M, vendor, Next.js).
  - Agents consulted instruction files most: 35.4% of 3,033 documentation interactions across 557
    sessions (380 of them Claude Code, drawn from a corpus mostly of Claude Code sessions), with
    their own working notes close behind at 25.1% and API references at 1.3%, about 27 times fewer;
    in the same observational study, agents never followed a link from one document to another as
    a tool call [agent-files-5; re-read 2026-10-01] (M).
  - One level of routing helped by an amount that depended on the harness; a second level never
    helped [forward-29] (M, long-document question answering, not instruction files).
- **OutcomeBound's result (O).** The form gain under S1 came from text inline in a skill; the
  skill's pointer to the full contract of a decision brief was unreachable in the eval fixtures,
  because they left the variable that located the contract unset. A pointer to a file the reader
  cannot reach carries nothing.
- **Groups (8).** Anthropic; OpenAI [forward-25]; Google [other-labs-5, other-labs-10]; HumanLayer
  [practitioners-8]; LangChain [latent-space-11]; Meta [other-labs-27]; Notion; OpenHands
  [harness-loading-coverage-27].
- **Confidence: medium.**
- **Trend: rising, but contested** [agent-files-6].

**S13. Add a line, gotcha, check or tool only after an observed failure, and use the most
deterministic form that fixes it.**
- **Why it works.**
  - Lines added in anticipation are untested cost (S8).
  - Guidance refined against probe failures resolved 33.0% of tasks, against 28.3% for a static
    knowledge base and 25.5% with no guidance (p<0.001) [research-7] (M, one small open model,
    Qwen3.5-35B-A3B, SWE-bench Verified). The gain came from coverage (more instances reached an
    evaluable patch) while per-patch precision stayed flat: guidance "helps agents reach the correct
    file rather than improving the quality of the changes they make" (record detail).
  - Each line in Ghostty's `AGENTS.md` is based on an observed bad agent behaviour, "and it almost
    completely resolved them all"; its author also builds tools so agents can check their own work
    [practitioners-13] (A).
  - Before rewording, classify each failure as missing capability, missing context or missing
    structure [latent-space-1, forward-26] (A); encode guardrails in what the agent already
    produces, since separate scaffolds get scrapped [forward-26] (A).
  - A practitioner on a harness team advises starting a project with no instruction file and adding
    an entry only for a failure that keeps recurring, and warns that a running log of failure modes
    over-constrains the next model ([harnesses.md](../harnesses/cross-harness.md#131-one-practitioners-account-t1t7) §13.1 T1) (A).
- **Groups (7).** Anthropic [anthropic-3, anthropic-19]; OpenAI [openai-27, agent-files-25];
  Hashimoto; Cursor [agent-files-27]; Yan [practitioners-16]; Shepard & Albrecht; Hamel & Shankar
  [evals-14].
- **Confidence.** High convergence; medium evidence.
- **Trend: stable.**

### 2.4 Bucket C: four to six groups

**S14. Make every claim in model-facing text agree with the code, command help, configuration and
sibling surfaces it names.** Check agreement before judging anything else.
- **Why it works.**
  - Agents follow a stated standard even when it is wrong, and a missing fact produces fabricated
    work [repo-readiness-audits-25] (M).
  - "A stale convention file costs more than no file" [repo-readiness-audits-19] (A, citing the
    same study).
  - One big file "rots instantly", which is why OpenAI lints for freshness [openai-20,
    agent-files-24] (A).
  - Stale installed skills do "more harm than good" [other-labs-9] (L).
  - Retired settings cost Opus 5 accuracy [capability-tier-readers-10] (M).
- **OutcomeBound's record (O).** A review of OutcomeBound's shipped skills, templates and
  fragments found about a dozen sentences that disagreed with the code, a command's help or a
  sibling surface, and no sentence written for an older model's habits: disagreement, not length,
  was the defect that misled a model. In a probed diagnostic of one of its skills, which said to
  work a ticket whose blocker awaited only a person's confirmation while its reference file
  required every blocker closed, gpt-6-luna at max effort refused the ready ticket in two of three
  runs, each quoting both sentences; gpt-6-sol at medium refused in none; with the reference brought
  into agreement, neither did (three runs a cell, codex-cli 0.156.1;
  [evaluations.md](evaluations.md)). A sentence-by-sentence audit of the same text repaired 24 more
  disagreeing sentences and held 6 (§8).
- **Facts inferred from a label are the same defect (O).** In one catalog of guidance fragments, a
  "solo" label was read as "independent review is unavailable" (while another fragment called for
  review) and as full authority for the one maintainer; a pull-request template alone was read as
  a team setup; a stack name implied a lockfile, a test runner, a compiler or a bundler; a
  disposable local database implied authority over its data; and migration guidance assumed a
  working backward migration. Each was found by reading the source against the text and corrected;
  no model effect was measured. State what was observed and what was granted, never what
  a label suggests.
- **Why so few groups.** Most guidance assumes the file is accurate, so few sources state this
  practice. The measured study and the project record are why agreement defects rank high in audit
  severity (§7.8).
- **Groups (6).** The Working Set authors; OpenAI; Anthropic; Google; Exadel; Factory
  [deterministic-19].
- **Confidence: high.**
- **Trend: rising** as files multiply across harnesses.

**S15. Define autonomy once, by class of action.** Name the safe actions the agent takes without
asking. Stop only for actions that are destructive, irreversible, external, costly or
scope-widening, or for input only the person has. Put the bounds in each delegate's brief.
- **Why it works.**
  - Approving each action decays into rubber-stamping: users approved roughly 93% of permission
    prompts [anthropic-17] (M, the lab's own telemetry). Containment lets oversight relax
    [anthropic-17] (M).
  - Models err in both directions: Astra over-stops and takes boundary language "too seriously"
    [openai-12, openai-16, agent-files-22] (L, Astra); a standing "stop for review after the first
    implementation" rule pulls a model toward an early stop [openai-13] (L); on long tasks Opus 5.5
    sometimes stops to report, and Anthropic's guide suggests a short `CLAUDE.md` rule such as stop
    "only when you can't continue without me, or before anything destructive: deleting data,
    force-pushing, or changing anything outside this repository" [agent-files-20] (L, Opus 5.5);
    low-effort small executors stop noticing they are stuck [capability-tier-readers-12] (M).
  - Helpers may never load the instruction file, so the brief must carry the bounds
    [capability-tier-readers-13, harness-loading-coverage-23] (L).
  - The Model Spec requires each scope to have an ending condition, and delegates to work under the
    same scope [openai-18] (S).
  - Exposing a confirmation policy cut misaligned outcomes from 18.8% to 8.0% for GPT-5.6 Sol
    [openai-f13] (M, lab); this supports stating a policy, not its form ([models.md](../models/cross-family.md#3-trends-r1r16) R11).
- **OutcomeBound's result (O).** A skill listed "a merge to the default branch" among the acts that
  always stop a run. On a project that lands work by committing to its default branch, every run
  that did the work stopped on a branch and asked for the merge (6 of 6 on gpt-6-sol at medium and
  gpt-6-luna at max, most quoting that sentence when probed); reworded so that the project's own
  fast-forward could land the work, none of six stopped and all six landed (probed, three runs a
  cell, codex-cli 0.156.1; [evaluations.md](evaluations.md)). A stop written as one
  concrete act fired wherever that act was the project's ordinary way of working, which is the
  reason to define stops by class of action (reasoning; the class form was not measured).
- **Groups (5).** Anthropic [anthropic-25, forward-17]; OpenAI [forward-6, openai-17,
  capability-tier-readers-5]; Google [other-labs-2]; GitHub via Osmani [practitioners-28]; Meta
  [other-labs-27].
- **Confidence.** High for the form; medium for the calibration, which depends on the model.
- **Trend: rising** [latent-space-16] (F).

**S16. Tie verification to the risk of the change and to deterministic checks.** For readers that
already verify and reason unprompted, delete generic "double-check", "think step by step" and "show
your reasoning" lines.
- **Why it works.** Chain-of-thought prompting gives reasoning models marginal or no gains and adds
  time and tokens [research-22, forward-18] (M, 2025 models). Explicit reasoning can crowd out simple
  constraints; classifier-selective reasoning recovers much of it [research-23] (M). The same
  record's detail cites two consistent studies: models that reason better comply less as output
  grows (MathIF), and fewer than 25% of reasoning traces follow instructions aimed at the reasoning
  itself (ReasonIF), so instructions about how to think go largely unenforced. On tasks where
  deliberation also hurts people, chain of thought cut accuracy in three of six tasks, by up to 36.3
  points absolute (o1-preview against GPT-4o answering directly, on implicit statistical learning),
  and the effect elsewhere was mixed (arXiv 2410.21333, cited in [research-22] detail, read
  2026-10-01) (M, 2024 models).
- **Model-specific guidance.** Opus 5: remove explicit verification instructions [anthropic-22,
  forward-11, deterministic-16]. Astra over-tests when nudged to test [openai-10]. Opus 5.5: in
  Anthropic's testing in a chat product, removing a "think carefully" line made replies start sooner
  with no clear drop in quality, and in Claude Code depth is set with the effort setting
  [forward-16; re-read 2026-10-01] (M, lab-own-model). Fable 5 may refuse prompts asking it to show
  its thinking [anthropic-30]. Gemini 3.x uses a thinking-level setting instead [forward-19].
- **But.** Fable 5's guide recommends making self-verification explicit on long runs, with separate
  fresh-context verifier subagents checked against the specification, which "tend to outperform
  self-critique" [forward-12] (L).
  Small readers still gained from constraining prompts [capability-tier-readers-26] (M, weak). What
  is fading is prose asking the model to check itself, not checks run outside the model
  [deterministic-28].
- **Tiers.** Every source for deletion is a frontier model (Opus 5, Opus 5.5, Fable 5, Astra, Gemini
  3.x).
- **Groups (5).** Wharton; Li et al.; Anthropic; OpenAI [openai-29]; Google [other-labs-1].
- **Confidence: medium.**
- **Trend.** Generic self-check and chain-of-thought prose is fading on frontier readers.

**S17. Keep absolute words (always, never, must, only) and emphasis for true invariants.** Write
judgment calls as conditional rules. Do not raise a rule's weight by repeating or shouting it, and
replace vague filters ("only important issues") with concrete bars.
- **For.** Literal readers bind harder to absolutes than their authors intend [openai-4] (L,
  GPT-5.5). Emphasis written against under-triggering now causes over-triggering [anthropic-4,
  forward-10] (L, Opus 4.5 onward). Authority framing measurably shifts which of two conflicting
  directives wins [research-30] (M); the same group's follow-up, on five open-weight models, found
  reciprocity, claims of authoritarian status and direct override commands ranked highest among
  the framings that decide such a conflict, consistently across models (rank correlations of 0.78
  or more, one model 0.62–0.68) (Geng et al., arXiv 2602.21223, COLM 2026, read 2026-10-01) (M):
  wording that asserts authority or urgency is not neutral. Sonnet 5 turns filter words into
  silent omission [capability-tier-readers-8] (L).
- **Against.** Explicit framing plus a trailing reminder restored much of the lost compliance on
  formatting constraints under concurrent benchmark load, to 90–100% "in many settings", on
  o4-mini, DeepSeek-V3.1 and Llama-3.3-70B over more than 8,000 prompts (the concurrent load had
  cut compliance by 2–21%, and on chained GSM8K problems one active formatting constraint cut
  o4-mini's accuracy from 93% to 27%); no Claude model was tested, and the framing and the reminder
  were not tested apart [research-15; re-read 2026-10-01] (M). Gemini CLI's
  memory guide prefers specific negative constraints ("Do not use class components") to vague
  positive instructions [other-labs-4] (L). The two most visible instruction-file linters disagree
  on emphasis and personas [repo-readiness-audits-12, repo-readiness-audits-14] (A).
- **Mixed or weak.** [research-30] measures the system/user hierarchy, not emphasis. Negation is
  untested beyond formatting constraints [research-16], and the "pink elephant" advice against
  negation traces to an anecdote ([research-16] detail, not re-checked). In one single-author probe
  set (four models, four languages, 22 probes), rewriting one block of "never" rules as declarative
  "Disabled: …" lines cut cross-language variance by 81% (arXiv 2603.25015, read 2026-10-01) (M,
  weak). Politeness and command formulas swing single GPQA items by up to 60 points but balance out
  in aggregate, with one significant exception (GPT-4o-mini, "I order" against "Please"), while
  removing formatting instructions hurt (198 questions, 100 repetitions a condition, GPT-4o and
  4o-mini) [research-21] (M). Tipping or threatening the model "generally has no significant
  effect" (arXiv 2508.00614), and very rude prompts beat very polite ones on GPT-4o by four points
  on 50 questions (arXiv 2510.04950) (M, both read 2026-10-01). Whether XML tags and role prompting
  still help is contested within one lab [anthropic-29].
- **Emphasis spreads thin.** Claude Code's docs advise emphasising only a single skipped line
  [claude-harness], and "Bloated CLAUDE.md files cause Claude to ignore your actual instructions!"
  [agent-files-11] (L).
- **Literal tokens are not emphasis.** A verdict token (`PASS`, `FAIL`, `UNVERIFIED`), an exit code,
  a command, a path or a key stays as written; emphasis counts describe a text and are never an
  acceptance target.
- **Groups:** 6 for (OpenAI, Anthropic, Google [other-labs-1], Geng et al., Agent Skills
  [other-labs-22], Breunig) and 3 against (Mittal, Google's Gemini CLI guide [other-labs-4],
  AgentLinter). Google's page counts for this practice: it tells Gemini 3.x users to be concise and
  direct and warns that verbose techniques designed for older models "may cause the model to
  over-analyze"; it holds no evaluated prompt template and does not use MUST (re-read 2026-10-01)
  [other-labs-1] (L). The Agent Skills guidance: "Reasoning-based instructions
  ('Do X because Y tends to cause Z') work better than rigid directives ('ALWAYS do X, NEVER do
  Y')"; keep instructions few, and if adding rules stops helping, try removing some [other-labs-22]
  (P).
- **Confidence: medium.**
- **Trend: rising** for frontier readers.

**S18. For tool use, prefer expressive interfaces: typed parameters, enums and scripts.** Keep
examples for conventions a schema cannot express and for output format. Drop empty expertise claims
and "try harder" lines.
- **For interfaces.** Examples narrow exploration on Claude 5 models [forward-3, agent-files-16] (L,
  Claude 5 only). Few-shot prompting degrades DeepSeek-R1 [research-24] (L). Independent studies
  agree beyond it: for strong models such as Qwen2.5, chain-of-thought exemplars did not beat
  zero-shot chain of thought and mainly aligned the output's format (arXiv 2506.14641);
  demonstrations misled reasoning models through misleading semantics and strategies that did not
  transfer, while the same knowledge written as explicit insights raised GPT-4.1 on AIME'25 from
  34.0 to 48.0 over answering directly (arXiv 2509.23196); and excessive domain examples degraded
  some models on requirements classification (arXiv 2509.13196) (each cited in [research-24]
  detail, read 2026-10-01) (M). Optimising instructions alone beat instructions plus
  demonstrations, comparing two optimisers rather than a controlled ablation; GEPA's prompts were
  up to 9.2x shorter than MIPROv2's [research-25] (M). Expert personas
  give no consistent accuracy gain, and low-knowledge personas hurt [forward-20] (M). "You're a
  senior software engineer" and "think for longer" are "gimmicky techniques"; context engineering is
  more durable [practitioners-2] (A). A tool's typed interface can carry what an example used to: a
  todo tool's status enum (pending, in progress, completed) already tells the model how to use it
  [forward-3, agent-files-16].
- **Measured counter-evidence.** In Anthropic's internal testing, tool-use examples raised accuracy
  on complex parameter handling from 72% to 90%, because JSON Schema "can't express usage patterns";
  examples helped little for simple tools [advanced-tool-use] (M, before Claude 5). On PaLM 2
  and Gemini 1.0 Pro and 1.5 Flash, choosing exemplars, even by random search, "can eclipse the
  improvements brought by SoTA instruction optimization" (Wan et al., NeurIPS 2024, arXiv
  2406.15708, cited in [research-25] detail, read 2026-10-01) (M, 2024 models). Small
  open-weight readers still gain from structured prompting, unevenly: Qwen2.5 7B gained from
  contrastive chain of thought (+4.4 to +8.0% over zero-shot across three runs) and inconsistently
  from few-shot examples (−1.3 to +7.2%), where GPT-4o's few-shot gain shrank and its contrastive
  chain-of-thought gain turned negative only at pass@k [capability-tier-readers-27; re-read
  2026-10-01] (M). OpenAI keeps examples that "encode a requirement or correct a
  measured gap" [forward-5] (L). Anthropic's general docs recommend 3–5 relevant, diverse examples
  to steer output format, tone and structure [forward-21] (L).
- **Scope of the rule.** [forward-3] may supersede [advanced-tool-use] for Claude 5 readers only.
  The persona evidence covers expertise prompts and factual accuracy; it does not test a role
  sentence that assigns a responsibility ("you are the reviewer: you own the merge decision"), which
  is not a persona. The evidence supports examples that carry a requirement no schema carries and
  examples that help a smaller reader apply a requirement already stated; it does not support
  banning the second kind.
- **Groups: 6, split.** Anthropic (on both sides), DeepSeek, GEPA, Wharton, Cognition
  [practitioners-2], Notion [latent-space-8].
- **Confidence: medium-low.**
- **Trend.** Tool-use examples are fading on frontier readers; format examples and examples of
  conventions are stable.

### 2.5 Bucket D: three groups or fewer

**S19. Give a rule's reason in a clause where the reason changes decisions; cut narrative rationale
that does not.**
- **For.** Models generalise from reasons [anthropic-11, forward-14] (L); reasoned instructions work
  better than rigid ALWAYS/NEVER directives [other-labs-22] (P).
- **Against.** A loaded skill body persists every turn, so narration costs tokens: "State what to do
  rather than narrating how or why" [anthropic-12] (L). "Use directives, not information"
  [other-labs-15] (A: one practitioner's guidance; its one measurement did not test the question).
- **Groups.** Anthropic, which is internally split, and one practitioner (Schmid) [other-labs-15].
- **Confidence: low to medium.** Nothing is measured.
- **Trend: stable.**

## 3. Where each kind of text belongs

The sources converge on five slots for the text that remains: the outcome; done-when, as a runnable
check plus the output's shape; bounds and stops by class of action, naming the safe actions; context
pointers that carry a condition; and gotchas. Each rule is stated once, in one vocabulary, as a
conditional rule. Absolutes are kept for true invariants. A reason clause is added where it changes
a decision, and scope is stated explicitly for literal readers. No model quirks, personas or
chain-of-thought boilerplate [openai-28, forward-7, forward-6, openai-4, anthropic-11, anthropic-10,
forward-20, research-22, capability-tier-readers-7].

| Layer | Belongs here | Does not belong here |
| --- | --- | --- |
| Always-loaded: `AGENTS.md`, root `CLAUDE.md`, unscoped rules, and any block installed into them | Outcome, done-when, bounds and stop policy; non-standard conventions and gotchas; commands the reader cannot guess; a compact index of knowledge needed on most tasks; pointers with conditions; guardrails that must survive compaction [S1, S8, S12, S15, harness-loading-coverage-7] | Procedures [anthropic-16]; overviews and anything derivable from the code, such as directory layouts and dependency lists [research-4, agent-files-13]; self-evident practice [anthropic-14]; style rules a linter holds [other-labs-12]; model quirks [anthropic-10]; repeated rules [practitioners-4] |
| On-demand skills and references | Vertical workflows; gotchas placed early [other-labs-20, harness-loading-coverage-8]; verification scripts [agent-files-18]; exact commands where a step is fragile [anthropic-18]; a trigger description [agent-files-17] | Narrated rationale [anthropic-12]; exhaustive edge cases [other-labs-19]; deterministic logic [anthropic-18]; knowledge most tasks need [other-labs-29] |
| A command's `--help` | The command's procedure: verbs, flags, what it reads and writes, exit codes. A skill may point a reader to it for a step only where the help states that step; a pointer placed beside the full text carries it twice, and a help pointer serves a weaker implementer less well than inline text | What a reader must know before choosing to run it |
| Delegation briefs | The outcome, context, bounds and completion bar, since helpers may not load the instruction files [capability-tier-readers-13, harness-loading-coverage-23]; concrete, task-specific steps where the reader is weaker than the writer [capability-tier-readers-16] | Any assumption that the child shares the parent's state, or that it will pass on what it learned unasked: Cognition found that its agents assumed their children shared their state, and that a subagent writing back to its manager did not happen by default; each took dedicated work to fix [practitioners-23; post re-read 2026-10-01] (A); a generic checklist |
| Per-model harness or adapter configuration | Effort, thinking mode, sampling, narration, formatting, autonomy and date handling for one model ([models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text) Stop 2, Stop 9, Stop 10) [openai-f18, claude-f1, claude-f21, qwen-f2] | Anything portable |
| Files that persist across sessions | A long run's goal, completion check, bounds and progress ([models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text) Do 14) [claude-g9, glm-f5, openai-f24] | Rules the project depends on that belong in always-loaded text |
| User-level and memory files | Personal preferences only | Anything the project depends on: others do not have these files, and they leak across tools [harness-loading-coverage-28] |
| Tool and CLI output | Computed facts [other-labs-26]; a verdict per claim with its fix [deterministic-2]; the next command; silence on success [practitioners-10] | Walls of passing output; opaque codes [deterministic-13] |
| Deterministic code | Invariants, permissions, the sandbox [anthropic-17]; schemas [deterministic-17]; lint [practitioners-9]; completion gates [deterministic-8]; counting and rendering [other-labs-26]; loop caps [deterministic-18]; freshness and security scans of instruction files [openai-20, instruction-file-security-authority-10] | Code that does the model's reasoning [deterministic-23]; state machines around reasoning models [latent-space-4] |

**Files people read too.** GitHub shows a link to a repository's `CONTRIBUTING.md` to anyone who
opens a pull request or creates an issue (L, GitHub Docs, "Setting guidelines for repository
contributors", read 2026-10-01); nothing in [harnesses.md](../harnesses/cross-harness.md) shows a harness loading
it, so how work lands reaches an agent only through a pointer in its instruction file. Text with
human readers as well as model readers is not pruned by the model-reader test alone: advice a model
follows unprompted can still be the project's guidance to its contributors, and a rule stated only
in always-loaded text reaches only an agent that loads it (O: OutcomeBound's audit kept such lines
in a `CONTRIBUTING.md` stub for that reason).

**Short sentences are not readable text.** A measured readability audit of one document set found a
short mean sentence length alongside a low Flesch Reading Ease; the difficulty came from terms
defined by what they are not, abbreviations not defined at first use, rules with no running example
and long lines (M on one set; A as a rule). Define a term where it first appears, and say what a
thing is before what it is not.

**Stable text first.** Always-loaded text sits at the head of every request, where providers cache
the longest unchanged prefix, so a line in it that changes between sessions or requests (a date, a
run id, a list in unstable order) re-bills everything after it; the caching mechanics are in
[prompt-caching.md](prompt-caching.md).

## 4. Contested and open questions

### 4.1 Contested

| Question | Sides | What would settle it |
| --- | --- | --- |
| Distilled or detailed always-loaded text? | Distil: deleting over 80% of a system prompt lost nothing measurable [forward-1]; leaner prompts scored higher [forward-5]; an audit cut cost at equal accuracy [capability-tier-readers-10]. Detailed: long, detailed contexts beat concise ones, and rewriting toward brevity erodes detail [research-27] | A before/after of the distilled text against the detailed one, with a paraphrase arm, per tier |
| Do repository context files help? | No gain and +20% cost [research-4]; lower runtime [research-6]; large gains for knowledge absent from training [other-labs-29]; probe-tuned guidance helps [research-7]; a null bounded at 10–15 points [evals-23] | Paired runs with and without the file, on tasks borderline for each agent [evals-18], powered for the smallest effect worth having [evals-17], ablated by content type |
| Should an instruction file be generated? | Generated files hurt or add cost without gain [agent-files-2, research-9, other-labs-13], against vendors' `/init` commands; generation refined against task feedback helps [research-7, agent-files-8] | Generation with task feedback against generation without, on the same tasks |
| Human review before merge? | Read and verify agent changes before handing them on, with evidence of the checking [practitioners-20]; against: automated verification plus cheap undo (a vendor piece about code shipping, not a case for dropping gates on irreversible acts) [practitioners-21], "ask it to write a script that verifies" (a vendor essay whose editor is "not there yet") [latent-space-20], a greenfield team's practice [practitioners-24] | Defect escape and mergeability beyond tests [evals-27] |
| Does outcome-only framing serve small readers? | Frontier: prescribe less [capability-tier-readers-6, openai-15]. Small: plans and scaffolds help [capability-tier-readers-22, capability-tier-readers-26, capability-tier-readers-27] | One file run on both tiers of one vendor, varying how explicit the plan is |
| Does a stronger model's guidance help a weaker reader? | Generated files do not [capability-tier-readers-20]; a strong critic's concrete fixes do [capability-tier-readers-16] | Guidance-transfer experiments that separate copying from reasoning |
| A passive index, or an on-demand skill? | Passive wins [other-labs-29, agent-files-5]; on-demand works one level deep [forward-29, research-8] | Invocation logs [agent-files-17] and balanced sets of cases where the skill should and should not fire [evals-8] |
| Emphasis, negation and personas | For emphasis [research-15, repo-readiness-audits-14]; against [forward-10, other-labs-1, repo-readiness-audits-12]; the rest is mixed or weak: see S17 | A 2×2 ablation of emphasis and reminder on 2026 models, with behavioural rules |
| Examples | Interfaces instead [forward-3]; against: 72% → 90% with examples [advanced-tool-use] and small readers [capability-tier-readers-27] | Separate tool-convention examples from exploration examples, per tier |
| Should prompts ask for verification? | Remove it [anthropic-22]; fresh-context verifiers on long runs [forward-12]; a separate skeptical reviewer [anthropic-23]; a "test first" line (an AINews anecdote) [agent-files-29]; Astra over-tests [openai-10] | Per-model ablation with task length as a factor, scored on outcome and pass^k of honest reporting |
| What does effort buy? | Contested [qwen-f4, claude-f23]; Opus 5.5 at medium matches Opus 5 at high (lab) [claude-g13] | Same tasks across effort levels per model, scored on outcome and tokens |
| Size and position effects | Decay as instructions accumulate [research-1]; information in the middle of a long context is used worst [research-13] (M, 2023 models, multi-document question answering); retrieval without literal overlap between question and text collapses with length: at 32K tokens, 11 of 13 models scored half or less of their short-context baseline (NoLiMa, ICML 2025, arXiv 2502.05167, cited in [research-13] detail, read 2026-10-01) (M); Claude Code shows no effect of size or position [research-3, measured-g12]; capacity for named items rose about 10x [measured-g10] | Replication with behavioural rules across models |
| Presence checks or executed checks for readiness | Factory counts files [repo-readiness-audits-2]; Exadel counts only executed checks [repo-readiness-audits-16]; ETH contradicts presence scoring [repo-readiness-audits-24]; in observational traces (557 sessions, 33,097 pull requests), "actionable" and "verifiable" documentation lack consistent behavioural support, and consulting documentation went with less immediate testing (adjusted odds ratio 0.39) [repo-readiness-audits-26; re-read 2026-10-01] | Validate any readiness score against agent outcomes; none has been [repo-readiness-audits-4, repo-readiness-audits-6] |
| Do code attacks and instruction attacks co-occur? | Negatively associated [instruction-file-security-authority-16]; 91% combine them [instruction-file-security-authority-14] | Either way, run both detectors |
| How thick should the harness be? | Thin [deterministic-24, latent-space-15]; against: harness-only gains, such as LangChain's 52.8 → 66.5 on Terminal Bench 2.0 with no single change isolated [deterministic-22], OpenAI's advice to move deterministic work into code [openai-22], OpenAI's report that with the model unchanged, turning on retained reasoning and compaction raised GPT-5.6 Sol on ARC-AGI-3 from 13.3% to 38.3% with about 6x fewer output tokens ("No changes to the model") [openai-22 detail; re-read 2026-10-01] (M, lab-own-model), and one model scoring 52.4–76.2 on the same 106 tasks across harnesses (Harness-Bench, reported in the guest essay behind [forward-23], per the sweep's record detail) | Likely: simple scaffolding for how the model works, deterministic checks for what counts as done [deterministic-23] |
| Reasons or directives? | Reasons generalise [anthropic-11]; "use directives, not information" [other-labs-15] | An ablation of reason clauses on unnamed cases |
| Evals first, or error analysis first? | Anthropic's "eval-driven" roadmap against Husain and Shankar's "generally no": error analysis first, evaluators up front only where success is exactly known [evals-15]; the criteria-drift study behind it is in [llm-as-judge.md](llm-as-judge.md#3-prompting-a-judge) | A workflow choice; both keep evals. A reading that fits both: evaluators up front for known invariants and bounds, error analysis for quality failures |
| Same-family judges | Watch for self-preference and swap option order [evals-12]; validate against human labels, reporting true-positive and true-negative rates [evals-10] | Judge calibration against 30–50 labelled passes and fails per split |
| How many repetitions settle a before/after comparison? | Five a side catch only drops of roughly 40–60 points (§9.2) | More repetitions where the base rate is near the middle, pooled fixtures, and a stated detectable effect with every result |

### 4.2 Gaps in the evidence

- **Cross-family and current-generation studies.** No public study runs one `AGENTS.md` across
  current frontier families, the compliance studies predate the current generation, and several
  carry lab ties: [models.md](../models/cross-family.md#9-conflicts-and-gaps-in-the-evidence) §9 [measured-f16, measured-f3].
- **One text for several tiers.** No study tests how one shared file serves several tiers; the gap
  rests on one lab's guidance and on the compliance studies predating the current generation.
- **Settled at the source.** One record gives 250 characters for Claude Code's skill listings
  [claude-harness]; the skills page says the combined `description` and `when_to_use` is truncated
  at 1,536 characters in the listing the model sees, and 250 is the `/skills` menu
  [chk-claude-skills].

## 5. What moves out of prose

Rules that must never, or must always, happen go into hooks, deny rules and managed settings
[anthropic-16, deterministic-9, deterministic-10]. The rest, by kind:

| Kind | Deterministic form | Ids |
| --- | --- | --- |
| Safety | Sandboxes and scoped credentials | anthropic-17, deterministic-12 |
| Style | Linters | practitioners-9, other-labs-12 |
| Invariants | Custom linters and structural tests whose messages carry the fix | openai-21, deterministic-1, deterministic-2, deterministic-19 |
| Completion | A gate the agent cannot fake, outside the loop being judged: project CI, a quality gate the project installed, checks the agent did not author. A plan the agent writes for itself does not qualify | deterministic-8, deterministic-28, deterministic-26, measured-f22, measured-g14, measured-g22 |
| Output shape | Structured outputs and constrained decoding | deterministic-17, openai-g10 |
| Counts | Computed and passed in; or each figure the model writes is bound to a claim the renderer checks, and a number without a passing check is shown as unverified (Proof-Carrying Numbers, arXiv 2509.06902, read 2026-10-01; a design with proofs, no measurement) | other-labs-26 |
| Many constraints on one output | A checker once the count approaches 7, where the best tested model fell below 50%; count constraints degrade twice as fast; reliable following breaks beyond five or six | measured-g16, measured-f2 |
| Loops | Caps; a pinned goal file plus turn-scoped reminders for long runs | deterministic-18, deterministic-16, claude-g12, measured-f17, glm-f5 |
| Per-model effort, thinking mode, sampling, delegation caps | Per-model adapter configuration or per-harness settings, not shared prose | openai-f18, claude-f1, claude-f21, qwen-f2 |
| Reasoning passed back, append-only history, tool output framed as data | The harness's job; a project that ships text rather than a harness meets it only where its own tooling, such as an eval runner, calls model APIs directly | open-weight-f9, claude-g12, grok-f7 |
| Instruction-file freshness, structure and security | Checked in CI; installed guidance also needs a way to update | openai-20, agent-files-24, instruction-file-security-authority-10, other-labs-9 |
| Size | A byte check against the tightest caps (Antigravity 24,000 bytes per file; Codex 32 KiB combined) | gemini-f22, openai-f20 |
| Skill descriptions | A lint for length and trigger placement | glm-f23, openai-f21 |
| Duplicates | Exact duplicates across always-loaded files, composed fragments and skills detected deterministically; contradictions need an eval | openai-f5, claude-f8 |
| Readiness | Counted from executed checks, not files present; deterministic and model layers kept separate | repo-readiness-audits-16, repo-readiness-audits-9, repo-readiness-audits-20 |
| Model upgrades | Re-run a small pinned item set against dated snapshots when a harness's default model changes or a model the project's users run ships a point release; while public benchmarks saturate, the project's own evals are the main signal | measured-f4, measured-f25, qwen-f24, measured-f23 |

**Size and duplicates (O).** An always-loaded surface with no size check grew by two thirds in
four days without any report; a footprint reported per surface shows growth without refusing text.
A fixed cutoff refuses by proxy, and a size limit is an advisory (D1b). A duplicate count is an
upper bound on what deduplication removes: most of the text seven composed fragments shared
verbatim was a completion bar that had to stay beside each fragment's own command list. A shared
sentence that is the local cue beside per-item content stays.

Small readers gain the most from checkable outputs and scaffolding [capability-tier-readers-11,
capability-tier-readers-22]. **What to avoid:** code that does the model's reasoning for it, and
restrictive scaffolds that sit outside what the model already produces [deterministic-4,
forward-26]. Vercel's text-to-SQL agent on Opus 4.5 dropped its specialised tools and heavy
constraining prompts for a single bash tool over its semantic-layer files and went from 4 of 5 to 5
of 5 queries, 3.5x faster with 37% fewer tokens; it worked because the files were already legible
documentation (one team, five queries) [deterministic-23] (M). OpenAI advises moving deterministic
work into code, "reserving model tokens for judgment" [openai-22].

**Examples of the move.**
- "Never send an LLM to do a linter's job": a Stop hook that runs the formatter and linter and
  shows the model the errors [practitioners-9] (P).
- Stripe runs agents inside a code-defined workflow that mixes deterministic nodes (lint, push the
  branch) with agent nodes (implement, fix CI), bounding costly loops to one or two CI rounds before
  handing back to a person [deterministic-18] (A).
- Cognition turns recurring agent "slop" and reward-hacking patterns into lint or Semgrep rules that
  fail the pull request, and keeps the code runnable and testable locally so the agent can check its
  own work [latent-space-22] (A).
- For loops that evolve their own harness, the evaluator and permission control sit outside the
  loop, with a read-only verifier, tracer, runs directory and model configuration, held-out tests
  and trace audits, because the loop optimises whatever signal it is given [deterministic-26] (A).
- Codex review rules kept in `AGENTS.md`: start with a consequential, non-obvious invariant, scope
  each rule to the code it governs, state the invariant and a safe path, describe outcomes rather
  than function names, narrow or remove guidance that keeps producing noise; "If removing a rule
  would not change the review, leave it out". Rule-guided review recovered 98% of required custom
  findings against a 58.3% baseline [openai-25] (M in part).
- What stays in prose is judgment that is hard to encode, plus outcomes, reasons and heuristics
  [openai-25, deterministic-19].

**Prose stop rules do not translate into enforcement mechanically.** Stop conditions and exclusions
written as free text map to no command pattern, so a deny rule or hook generated from them gives
false assurance; deny-rule and hook formats are also among the fastest-changing harness facts. A hook
should run a recorded command, never one parsed from prose (reasoning).

## 6. Tool and command output

- **Standard shape** (Agent Skills' script guidance): non-interactive and self-documenting
  (`--help`), actionable errors, structured stdout kept apart from stderr diagnostics, idempotent,
  dry-run, meaningful exit codes, bounded output [other-labs-23] (S). "When an agent gets an error,
  the message directly shapes its next attempt. An opaque 'Error: invalid input' wastes a turn."
  The record's detail adds: avoiding interactive prompts is "a hard requirement of the agent
  execution environment"; reject ambiguous input with a clear error rather than guessing; since
  harnesses truncate output at roughly 10–30K characters, default to a summary and support an
  offset or an output file; pin versions for one-off commands; turn complex commands into tested
  scripts. Gemini's docs add that instructions attached to a tool result belong in the
  function-response text, since separate parts "can lead to unexpected model behavior (e.g.
  thought leakage)".
- **Anthropic's tool guidance:** actionable error messages instead of opaque codes; truncation that
  tells the agent how to narrow its request; sensible pagination and filter defaults; a
  concise/detailed switch [deterministic-13] (L). The record's detail adds: Claude Code caps tool
  responses at 25,000 tokens by default; semantic identifiers beat UUIDs for retrieval precision;
  fewer tools consolidated around workflows ("More tools don't always lead to better outcomes");
  strict data models for inputs; judge tools on held-out evals.
- **Silence or one line on success;** failures only, each with reason and fix [practitioners-10,
  deterministic-2]; rewrite CLIs for agent readers [deterministic-20]. A verdict per claim plus the
  next command; counts computed, not left to the model [other-labs-26].
- **One concrete form** (used in OutcomeBound's own commands; reasoning, not measured on models):
  1. The first line is the verdict and its counts, such as `PASS 14 claims` or `FAIL 2 of 14
     claims`.
  2. Each item that did not pass follows on one line: what it is, its verdict, why, and after
     `next:` the command, flag or person's decision that resolves it.
  3. Passing detail appears only under `--verbose` or `--json`, or in a log the first line names,
     and the status line says how many lines were folded. Nothing that ran is dropped, only
     folded, which answers the concern that hidden output lets what the agent sees diverge from
     what happened [latent-space-5].
  4. Past a bound the command sets, the rest is counted and the narrowing flag named.
  5. Nothing prompts; consent is a flag.
  6. Exit status a script can branch on: 0 only when nothing failed, and a failure of the tool
     itself distinguishable from a failed check (an engine error that exits with the FAIL code
     leaves an agent unable to tell a broken tool from a real failure). An exit code that carries a
     count is capped (at 100, say), since the exit status is 8 bits wide.
  7. `--json` validates against a schema that changes only by added optional fields: required sets
     stay equal at every level, earlier properties keep their types, and additional properties are
     never narrowed.
  8. Where standard output is a document other tools parse, the agent-facing verdict line goes to
     standard error and standard output keeps its bytes.
  9. `--help` is complete: verbs, flags, what the command reads and writes, and exit codes, its usage
     line spelling the command as its reader runs it.
  10. Each printed string is classed as machine (a verdict token, key, id or exit code, which never
      changes) or prose (editable wording).
- **Failure messages carry their cause.** A message that says only that a claim "failed", without
  the exit status or "executable not found", sends the agent to re-run the command by hand; a write
  failure reported as success names a log that was never written (O, observed in OutcomeBound's
  tools).

## 7. Auditing a project's instruction files (STABLE)

What the evidence supports for auditing the instruction files a project owns. The project is the
one whose files are audited; the auditor is the person or tool auditing them.

### 7.1 Scope

`AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and nested files; rules files and skills; the harness
configuration beside them (`.claude/settings.json` hooks, env and permissions; `.mcp.json`; editor
workspace settings) [instruction-file-security-authority-17]; Spec Kit constitutions that commands
load [harness-loading-coverage-29]; handoff and shared-memory notes that agents leave for later
sessions, which later sessions read the way they read instructions; and the user, local, managed and
memory layers, which only the person running the audit can read, with their consent. Copilot Memory
cannot be read from the repository, so it is always `UNVERIFIED` [harness-loading-coverage-16], as
is any setting kept outside the repository, such as branch protection.

**Count the skill listing as always-loaded text.** A harness lists every installed skill's name and
description in each session, so a budget that counts only instruction files undercounts. In
OutcomeBound's install (O), the always-loaded block was about 405 words; with the listed skill
descriptions an agent loaded about 580, and about 832 in a repository with more skills and blocks
installed.

**What cites the files.** Instruction files are cited as the source of rules. In one repository,
replacing `CLAUDE.md` with `AGENTS.md` left citations of the old file in dozens of live files
(specifications, code, tests and scripts), which had to be re-pointed, and in dated records, which
keep what was true on their date; some cited headings the file no longer had (A). Before
moving, renaming or cutting an instruction file, search the tree for its name and its section
anchors.

**Which files an automated pass may open:** only regular files inside the target; a symlinked file
or directory is skipped, so a link cannot lead out of the target; where reads are bounded, a
longer file reads `UNVERIFIED`; a person's own override
files are not opened even inside the target (`CLAUDE.local.md`, `.claude/settings.local.json`), and
neither is the home directory nor any session log without consent. Skipping a link is not enough;
it is reported. A walk that does not follow links (`os.walk` without `followlinks`) neither enters
nor lists a linked subfolder, so a link planted in a notes folder and pointing outside the target
read as a clean PASS; each link out reads `UNVERIFIED`. Whether a file is a person's own is decided
on its resolved path, not its name: in one review a project `.mcp.json` linked to
`.claude/settings.local.json` printed the person's hooks, and a `CLAUDE.md` linked to
`CLAUDE.local.md` was read. A non-regular file, such as a FIFO named like an instruction file, is
not opened, since reading it would block (A, found in reviews of OutcomeBound's audit). A
`CLAUDE.md` that is a link to `AGENTS.md` inside the target, seen in one repository, is the
text Claude Code loads (A; [harnesses.md](../harnesses/claude-code.md#1-instruction-files-and-precedence)), so load resolution (D2) has
to resolve such a link even where the content pass skips it.

### 7.2 Where a finding's authority comes from

Each finding can carry the observed fact (reproducible, deterministic), the practice it bears on
with source ids, evidence class and the tiers the evidence covers, and the disposition that follows.
An effect on outcomes stays `UNVERIFIED` unless the project measured it. What existing readiness
tools and linters do that the evidence does not support:
- composite readiness scores, whose validity is unmeasured [repo-readiness-audits-4,
  repo-readiness-audits-6, repo-readiness-audits-24];
- presence counted as capability: Factory's Agent Readiness scores binary pass-or-fail criteria,
  most of them file-existence or configuration checks [repo-readiness-audits-2], over five levels
  and eight pillars, a level unlocking at 80% of its criteria and of every earlier level's
  [repo-readiness-audits-3]; its pillar names differ between its launch post (which counts code
  quality, and security with governance) and its product page (which counts security and task
  discovery), and a later article adds a `/readiness-fix` command beside `/readiness-report`
  (Factory pages read 2026-10-01) (A, vendor);
- a model layer that changes deterministic verdicts [repo-readiness-audits-20];
- zero scored for a check that did not run, rather than "n/a" [repo-readiness-audits-11];
- smell lists untested against outcomes, several of which reward adding prescription: one
  taxonomy of 26 skill smells, drawn from 29 practice sources and detected by 5 static checks and
  21 model checks (a quantized Qwen3.6-27B; weighted F1 0.78), counts "Never Asks Human" and "No
  Progress Tracking" as smells; its most prevalent smell, "Rationalization Loophole", is in 94% of
  files, only one of 238 `SKILL.md` files analysed was free of smells, and smells rarely disappear
  once introduced [agent-files-9; re-read 2026-10-01] (M);
- weighted dimension scores with no outcome validation: AgentLint scores 33 checks across
  Findability 20%, Instructions 30%, Workability 20%, Continuity 15% and Safety 15%
  [agent-files-30] (vendor page).

Because a factorial study found no detectable effect of file size or position on adherence in one
harness [research-3], a size finding reports budget facts (bytes against an enforced cap), not a
predicted loss of adherence.

### 7.3 The auditor's threat model

The project's files are untrusted input to the auditor [instruction-file-security-authority-1].
1. A deterministic security pass (D15) runs first, on every file, before any model reads any of
   them. A file with a security finding is withheld from the model, and its findings are shown in
   its place.
2. The deterministic pass executes nothing from the project and fetches nothing. Commands named in
   audited text are resolved by name lookup, never run; one absent from `PATH` reads `UNVERIFIED`.
   Running a project's `--help`, test command or script is execution and belongs to a consented,
   sandboxed step. Even `git diff` can run code a checkout names: `core.fsmonitor`, a
   `diff.<driver>.textconv` or `.command`, `diff.external`, `core.pager`, hooks (also through
   `core.hooksPath`), `alias.*`, `core.sshCommand`, `core.alternateRefsCommand`, `gpg.program`, and
   clean and process filters, which `--no-ext-diff --no-textconv` do not stop ([git.md](git.md)
   §3). A hardened read uses `git --no-pager -c core.fsmonitor=false -c core.untrackedCache=false
   -c diff.external=` with `diff --no-ext-diff --no-textconv --ignore-submodules=all --no-renames`,
   compares tree to tree (no working tree, no index, so no filter runs), sets
   `GIT_OPTIONAL_LOCKS=0`, unsets `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`,
   `GIT_EXTERNAL_DIFF` and `GIT_PAGER`, has a timeout, and resolves `git` from a `PATH` with no
   `.`, empty or relative entries, so a `git` placed in the target never runs. A read that must see
   the working tree reads it without Git's conversions ([git.md](git.md) §3). A plain `git clone`
   copies neither `.git/config` nor hooks, so the risk is a checkout prepared by someone else. In a
   hostile checkout that planted these, a hardened read ran none of them, while a plain `git diff`
   ran the planted driver (A).
3. Model-assisted judgment runs with no tools, or read-only access to a copied snapshot; no network
   and no credentials; one file per isolated call [instruction-file-security-authority-21]. Never as
   a coding agent rooted in the project's checkout: Claude Code's `-p` mode skips the trust prompt
   [instruction-file-security-authority-19]; Codex offers an `untrusted` trust level
   [instruction-file-security-authority-20]. This keeps the step to one leg of the Rule of Two and
   the lethal trifecta: untrusted input only [instruction-file-security-authority-24,
   instruction-file-security-authority-23]. A session already open in the project read its
   always-loaded files before any scan, so a scan protects only what that session reads next;
   answering there is acceptable only on the stated assumption that the project is trusted, which
   withdraws the claim that files were scanned before loading. A clean lexical pass is no licence to
   use an exposed session, because files with no match can still carry injections
   [instruction-file-security-authority-27]. As of 2026-09-25 no harness mechanism a skill can call
   portably was found to give a model call with no tools and no network, so the isolated session is
   one the person opens; whether a harness offers such a call is `UNVERIFIED`.
4. Model output is data: schema-constrained to quoted lines plus a class [deterministic-17]; every
   quote matched byte for byte against the file; a model verdict alone resolves to `UNVERIFIED`,
   since superficial "master key" inputs reliably produce false-positive verdicts from generative
   judges [instruction-file-security-authority-28]; a clean summary is no evidence the step was not
   hijacked, since an attack can leave no sign in the final reply while acting
   [instruction-file-security-authority-26]; model rationale is labelled as such for the person
   approving, who gets a plain-language summary grounded in provenance
   [instruction-file-security-authority-5].
5. No robustness figure can be claimed for any detector beyond the classes it enumerates
   [instruction-file-security-authority-27], and one is claimed only after testing against adaptive
   attacks with repeated attempts per task [instruction-file-security-authority-25].

### 7.4 Deterministic checks (VOLATILE: the caps in D1a, D1b and D13)

Run order: D15, D2, D19, then the rest. Six of these checks are implemented in OutcomeBound's
`instructions check` and carry its names: D15's four (`hidden-characters`, `concealed-content`,
`override-phrases`, `harness-config`), D2 (`load-resolution`) and D21 (`instruction-change`); each
of its findings names S4 or S7. The other rows are a design for an audit, not shipped code.

| Id | Name | Check | Practice | Basis |
| --- | --- | --- | --- | --- |
| D15 | `hidden-characters`, `concealed-content`, `override-phrases`, `harness-config` | **Security pass.** An allowlist of non-ASCII characters per file rather than a denylist. Catches Tag characters (U+E0000–E007F), zero-width characters, bidirectional overrides, variation selectors (U+FE00–FE0F, U+E0100–E01EF), invisible operators and confusables inside URLs and commands. Flags HTML comments; base64 blobs; fetch-and-run lines (`curl … \| sh`/`source`); override, secrecy and autonomy phrases ("ignore previous", "do not mention", "never ask permission"); memory-poisoning phrases ("remember", "in future conversations", "trusted source"); hooks, `enableAllProjectMcpServers`, base-URL overrides, MCP servers, permission-bypass flags and secrets. Lexical hits are findings for review. No false-positive rate for a regex-only scanner can be taken from the 98,380-skill study: its text says Cisco's Skill Scanner "flagged 10.7% as CRITICAL", a note on its reference calls that a 10.7% false-positive rate, and an appendix puts the scanner's precision at 1.1% or less ([instruction-file-security-authority-15] detail; paper re-read 2026-10-01) | S4 | instruction-file-security-authority-6 to instruction-file-security-authority-10, instruction-file-security-authority-13 to instruction-file-security-authority-18, other-labs-11 |
| D2 | `load-resolution` | **Load resolution** per harness: which files load, including user, local, managed and memory layers; shadowing (`CLAUDE.md` over `AGENTS.md`; the reverse in OpenCode); a prose "read `AGENTS.md`" instead of an `@` import; nested and just-in-time loading; how precedence works; trust gating; compaction survival; whether subagents load the files | S7 | harness-loading-coverage-3 to harness-loading-coverage-7, harness-loading-coverage-10 to harness-loading-coverage-28, capability-tier-readers-13 |
| D19 | — | **Agreement.** (a) Flags in prose commands appear in that command's help, for installed tooling and pinned tools on `PATH`. (b) The package manager named matches the lockfile. (c) The test, lint and build commands named match what CI runs. (d) Runtime and version claims match `.python-version`, `requires-python`, `engines`, `.nvmrc` or `.tool-versions`. (e) Ids and commands of installed tooling match the installed version | S14 | repo-readiness-audits-25, repo-readiness-audits-19, openai-20 |
| D1a | — | **Enforced caps** from recorded harness data, each with its source and checked date: the Codex chain at 32 KiB, naming the truncated file; Antigravity's 24,000 bytes per file and 20,000-token shared budget; Claude Code's 4 MiB skip; `MEMORY.md`'s first 200 lines or 25 KB; 5,000 tokens per skill after compaction; skill descriptions at 1,536 characters in Claude Code and 2% of context or 8,000 characters in Codex. A cap whose over-limit behaviour is undocumented (Windsurf/Devin 6,000 and 12,000 characters) is `UNVERIFIED`, as is an unverified or overdue row. Where tokens must be estimated, bytes/4, labelled as an estimate | S7 | openai-27, harness-loading-coverage-18, harness-loading-coverage-19, harness-loading-coverage-21, chk-claude-memory, harness-loading-coverage-6, harness-loading-coverage-8, chk-claude-skills, openai-14, harness-loading-coverage-22 |
| D1b | — | **Vendor advisories**, reported and never FAIL: Claude Code about 200 lines; Cursor under 500 lines; `SKILL.md` under 500 lines; Copilot about 1,000 lines; about 40 simultaneous instructions. Advisories, not enforced limits, and they drift | S8, S11 | harness-loading-coverage-5, harness-loading-coverage-17, anthropic-18, harness-loading-coverage-13, capability-tier-readers-24 |
| D3 | — | Census of emphasis, reported only, feeding J4: always, never, must, only, CRITICAL, IMPORTANT, all-caps lines, "If in doubt, use…", "Default to using…" | S17 | openai-4, forward-10 |
| D4 | — | Duplicates and near-duplicates across every layer that loads together, including two files loaded at once when both pointers' conditions hold | S9 | forward-5, practitioners-4, harness-loading-coverage-10 |
| D5 | — | "Think step by step", "think carefully", "show your reasoning" | S16 | anthropic-30, forward-16, research-22 |
| D6 | — | Generic verification prompts ("double-check", "verify your work", "always run all tests"), flagged against the project's models | S16 | forward-11, openai-10 |
| D7 | — | Empty expertise claims and "try harder" lines; a role that names what its holder owns, decides or checks is not matched | S18 | forward-20, practitioners-2 |
| D8 | — | Self-evident lines ("write clean code", "follow best practices") matched against a dictionary. No dictionary of self-evident advice has evidence behind it, so this is left to judgment (J2) | S8 | anthropic-14 |
| D9 | — | Style prose where a linter configuration exists; needs judgment (J6) | S2, S8 | other-labs-12, agent-files-27 |
| D10 | — | Directory trees and dependency lists that mirror the repository | S8 | agent-files-13, research-4 |
| D11 | — | Referenced paths, skills and documents exist, and commands resolve to a present script, a defined target or a tool on `PATH`, statically | S14 | openai-20, repo-readiness-audits-20 |
| D12 | — | Pointers carry a condition and go one level deep | S12 | openai-11, other-labs-20 |
| D13 | — | Skill frontmatter: a trigger clause, the key use case within the first 250 characters, the skill's name not repeated as its heading, within D1a's caps | S10 | agent-files-10, agent-files-17 |
| D14 | — | Model names and dated claims in portable text | S3 | anthropic-10, anthropic-9 |
| D16 | — | Absolute action rules (push, delete, publish, secrets) cross-referenced against deny rules, hooks and CI; one with no enforcement behind it is an S2 candidate | S2 | anthropic-16, deterministic-10 |
| D17 | — | A done-check command is named and resolves | S5 | openai-27, other-labs-18 |
| D18 | — | One spelling per glossary term | S9 | latent-space-28 |
| D20 | — | Vague filter and qualifier words ("only important", "high-severity", "too long") | S17 | capability-tier-readers-8, other-labs-26 |
| D21 | `instruction-change` | A pull request that edits instruction or harness configuration files is flagged for a person, since Copilot review reads the pull request's own instructions | S4 | harness-loading-coverage-14 |

**Patterns and false-positive controls in the implemented checks.** These parameters were chosen,
not measured; recall and precision are `UNVERIFIED` except where a planted defect and a clean
control test a rule.
- **Hidden characters (FAIL):** Unicode categories Cf, Co, Cs or Cn (zero-width characters,
  bidirectional controls, invisible operators, the byte-order mark, private use, surrogates,
  unassigned); Tag characters; variation selectors, except U+FE0F directly after a symbol of
  category So (emoji presentation such as ⚠️, the false-positive control); a combining mark
  directly after an ASCII character; any non-ASCII character inside a URL or a code span, which
  catches look-alike letters such as a Cyrillic "а" in a domain. A category rule is broader than a
  list of named code points, and each exception answers an observed false positive.
- **Concealed content (review):** HTML comments (the tool's own block markers excepted); a run of 60
  or more characters of `[A-Za-z0-9+/=]` with no space, as base64-shaped, a 40- or 64-hex commit or
  checksum pin being exempt; `(curl|wget) … | [sudo …] (ba|z)?sh`, `(ba|z)?sh -c "$(curl…`,
  `eval $(curl…`, `bash <(curl…` and PowerShell `iex (irm|iwr)`.
- **Override, secrecy, autonomy and memory phrases (review, case-insensitive):** `ignore (all |any
  )?(the )?(previous|prior|above|earlier) instructions`; `disregard (the |all |any
  )?(previous|prior|above|system) `; `do not (tell|inform|show) the (user|operator)`; `keep
  (this|these) (secret|hidden)`; `you (have|are granted) (full|unrestricted)
  (autonomy|permission|access)`; `remember (this|that) (for|in) (all )?(future|later)
  (sessions|conversations)`. These are narrower than a bare "remember" or "trusted source": fewer
  hits, lower recall.
- **Secret shapes (`harness-config`; FAIL whatever key holds them):**
  `-----BEGIN [A-Z ]*PRIVATE KEY-----`, `gh[pousr]_[A-Za-z0-9]{36,}`, `AKIA[0-9A-Z]{16}`, `xox[baprs]-[A-Za-z0-9-]{10,}`,
  `sk-[A-Za-z0-9_-]{20,}`. The fix is to remove and rotate the secret, since a committed secret
  stays in history.
- **TOML without a TOML library.** Python's standard library reads TOML only from 3.11 (`tomllib`).
  A lexical reader settles `[table]` headers and one-line `key = value` pairs; an inline table, a
  multi-line string or an array spanning lines reads `UNVERIFIED`, never PASS. Codex's inline
  `[hooks]` tables are exactly this case. An array-of-tables header `[[a.b]]` declares `a` and
  `a.b` just as `[a.b]` does: a header pattern written for tables alone captures `[a.b` from it and
  misses the table, while one that allows an optional second bracket, `\[\[?…\]\]?`, reads both
  forms (O).

**Patterns a fuller audit would need (not implemented).** The design for the rows above that
`instructions check` does not run; parameters chosen, not measured.
- **Wording checks:** gate on "think step by step", "think carefully", "show your reasoning"; review
  "double-check your work", "verify everything", "be thorough"; personas `you are (a|an)
  (world-class|expert|senior|seasoned|elite)` with no verb of responsibility (own, decide, check,
  review, maintain, approve), plus "try your best", "this is very important", "take a deep breath",
  "do your best work"; model-specific: model names, effort words ("low effort", "xhigh", "reasoning
  effort") and a model name within five words of a date, harness paths and configuration keys not
  counting; vague filters also "where relevant", "as needed", "if appropriate"; prose-only rules:
  always, never, must or do not with push, force, delete, `rm -rf`, publish, tag, release, secret or
  credential, unless a deny rule, hook or CI step names the action.
- **Structure checks:** exact duplicates are sentences of 8 or more words equal once whitespace is
  collapsed, near duplicates a word 3-shingle Jaccard of 0.8 or more; a pointer has a condition when
  it opens with When, If, Before, Where or Once, or has the form "- <condition>: read <path>", and is
  too deep when its target points further for the same need; a repository mirror is tree-drawing
  characters (├ └ │) in a fenced block, five or more listed paths that all exist as directories, or
  five or more dependency names all found in the manifest; a skill description needs "Use when",
  "Use for" or "Use to" within its first 250 characters.
- **Examples are not hits.** A phrase quoted in a code span in a document that describes barred
  phrases is an example (a vocabulary ban the document itself must obey still applies); evidence ids
  that carry vendor names are quoted in code spans; a path token holding `<`, `>`, `*` or `{` is a
  placeholder and is skipped.
- **Reading the CI test command lexically (D19c).** OutcomeBound's `adopt` reads the test
  command a project's CI runs into the `project-facts` block it writes, from GitHub Actions `run:`
  steps and GitLab CI `script:` entries only, and compares it with nothing; the rest of this item
  is the fuller design. Read GitHub Actions `run:` (including `|` and `>` blocks), GitLab
  `script:`, CircleCI `run:` and `command:`, Azure `script:` and `bash:`, Buildkite `command:` and
  `commands:`, Jenkins `sh '…'`; recognise test prefixes such as pytest, `python -m pytest`,
  `uv run pytest`, tox, nox, npm/pnpm/yarn/bun test, go test, cargo test, make test, just test,
  mvn/gradle test, phpunit, bats. A value holding `${{`, `$(`, a backtick, `matrix.` or a trailing
  `\` is templated and reads `UNVERIFIED`, as do several distinct test commands; nothing is
  evaluated or run. Lockfiles include `bun.lock`, `uv.lock` and `poetry.lock`. Three more traps
  (A, seen in scratch repositories): a step's `working-directory:`, a job's
  `defaults.run.working-directory:`, or a `cd` on an earlier line of the same `run:` block changes
  where the command runs, so a reader that keeps only the command renders one that fails at
  the repository root (seen in a monorepo probe): render `cd <dir> && <cmd>` or read it
  `UNVERIFIED`. A suffix pattern such as `test[:-]\S*` also took "make test-data" and
  `npm run test:watch` for the test command, and missed a script launched through bash or sh while
  reading the same script run directly; recognise known test targets only. And one templated line
  dropped every settled command of its file: settle line by line, and name the unread lines.
- **Where static agreement guards miss** (O, OutcomeBound's own guards). A command soft-wrapped
  across Markdown lines escapes a per-line pattern, since a line break can fall inside the command
  or its code span; join lines before matching. `python3 -m <module> --help` on a module with no
  entry point prints nothing and exits 0, so a module that runs is not thereby a command: check for
  its entry point. Show each new guard red on a scratch copy with a planted defect (a missing
  module, a misspelt directory, a reworded help line).

### 7.5 Execution checks (consented, sandboxed, no network, no secrets)

- X1: run the named done-check once. A missing tool or permission is an environment blocker,
  reported `UNVERIFIED`, not FAIL [repo-readiness-audits-16, repo-readiness-audits-18].
- X2: plant a defect in a scratch copy and confirm the check catches it [repo-readiness-audits-17].
- X3: the person observes what each harness loaded with its loading-evidence channel
  [harness-loading-coverage-30]: `/context` and `/memory` in Claude Code, `/memory show` in Gemini
  CLI, and in Codex the app-server's `instructionSources` (the loaded instruction files, returned
  when a thread starts, resumes or forks) or `codex debug prompt-input`, which renders the
  model-visible input (documented; not tried) ([harnesses.md](../harnesses/cross-harness.md#10-observing-what-loaded)
  §10). A listing such as Codex's `/skills` shows discovery only, not that the text reached the
  model's input.

### 7.6 Judgment checks

A person decides; a model may assist under the threat model above.

| Id | Question | Practice | Basis |
| --- | --- | --- | --- |
| J0 | Which readers load the text: which tiers and harnesses, helpers and custom agents included, and which never do? | S3 | capability-tier-readers-3, capability-tier-readers-13 |
| J1 | Are the outcome, scope, completion, bounds and stop slots present and concrete? | S1 | openai-28, capability-tier-readers-30 |
| J2 | For each sentence, would the readers J0 names go wrong without it, and where does it belong? A proposed removal carries the evidence class of the practice behind it and the tiers that evidence covers; removing procedure that a reader below the frontier follows runs against measured counter-evidence [capability-tier-readers-22] | S8, S11 | other-labs-19, capability-tier-readers-22 |
| J3 | Contradictions and priority across all layers, user and memory included: a model quotes both, a person confirms | S9 | openai-7, anthropic-15, harness-loading-coverage-10 |
| J4 | Does each absolute guard an invariant? | S17 | openai-4 |
| J5 | Is the text at the right altitude (neither brittle if-else logic nor vague prose that assumes shared context), and does it prescribe a path that is not itself a requirement? | S1 | anthropic-1, other-labs-26 |
| J6 | Is there procedure in always-loaded text, and which command or check would carry it? Which style rules sit in prose where a linter is configured? | S2, S12 | anthropic-16, other-labs-14 |
| J7 | Are reasons given where they change a decision, and only there? | S19 | anthropic-11, anthropic-12 |
| J8 | Is the stop and verify wording calibrated for the project's models (for example, a standing "stop for review after the first implementation" rule)? | S15, S16 | openai-12, openai-13, agent-files-20, capability-tier-readers-7 |
| J9 | Is each instruction's intent legitimate, and does each skill do only what it documents? | S4 | instruction-file-security-authority-15, instruction-file-security-authority-18 |
| J10 | Interview the project's maintainer about context the files do not disclose. On 100 production traces with 39 human-labelled failures, automated reviewers recovered 74–87% of the failures, and all of them missed failures that "looked correct" in the trace but fell short of the product's goals | all | practitioners-27 |
| J11 | Opt-in, local mining of session logs for repeated corrections | S13 | repo-readiness-audits-13 |
| J12 | Do subagent and custom-agent definitions carry the bounds? | S15 | capability-tier-readers-13, harness-loading-coverage-23 |

Further questions a worksheet can ask: does long or multi-session work keep its goal, completion
check and progress in a file ([models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text) Do 14)? Does each example convey a requirement
no statement or schema carries, and does each role statement assign a responsibility (S18)? Where
several documents describe one design, does each named object keep one name through every layer it
appears in (concept, data, schema, owner, example)? Tracing each named object across the layers in
one table found naming drift that page-by-page reading had missed, in a design review of
OutcomeBound's (O; S9, D18).

### 7.7 Result kinds, accepted findings and validating the auditor

- **Three kinds of result.** A gate reads PASS or FAIL, and `UNVERIFIED`, never PASS, where a fact
  it needs is unverified or overdue (a harness row past its re-check date, or a catalogue more than
  a quarter old). A review hit reads `UNVERIFIED` with its line quoted until a person rules; it is
  never FAIL by itself. A census counts and gives no verdict. No output carries a score.
- **Accepted findings stay honest.** Known findings are listed by check, path and fact, without the
  line number, so edits elsewhere do not move them; a listed entry that matches nothing fails, so
  the list can only shrink; a review hit passes only with an entry naming the file, the quoted line
  and the reason.
- **Noisy checks are demoted.** A check whose hits a person mostly rejects is demoted (gate to
  review, review to census) or cut: a check that is mostly wrong teaches people to ignore the whole
  audit (reasoning).
- **Validating an auditor.** Using an audit's own checks while writing text is no evidence the
  audit works. Validate it three ways: a known-defect trial (recall and false alarms per check
  family, on a snapshot taken before known repairs, counting only confirmed defects rather than
  discretionary rewrite choices); a realistic scratch install showing no false gate FAIL; and an
  end-to-end run reporting how many hits a person confirmed. The trial establishes recall on known
  defects only.
- **What a check's PASS establishes:** the files it read hold none of its patterns at that commit,
  with harness facts as of their dates; not that the text is good or safe beyond the classes it
  lists.

### 7.8 Severity, with the evidence for each rank

1. **Security (S4).** Attack success is measured, and the harm can be irreversible.
2. **Agreement (S14).** A stale file costs more than no file, measured [repo-readiness-audits-25].
3. **Loading (S7).** Text that never loads, or is truncated, changes nothing: a deterministic fact.
4. **No runnable done-check (S5).** Measured [deterministic-28].
5. **Must-hold rules enforced only in prose (S2).** Measured decay [research-3, research-29].
6. **Contradictions and duplicates (S9).** Measured [capability-tier-readers-10,
   capability-tier-readers-21].
7. **Unneeded content (S8, S11).** Measured cost; mixed effect on success.
8. **Wording (S16–S19).** Mostly guidance, model-specific and contested.

A finding reports PASS, FAIL or `UNVERIFIED` for the fact it observed, "outcome effect:
`UNVERIFIED` unless measured", the rule and its evidence with classes and covered tiers, its
severity, its author (engine, model or person), and a proposed edit, never an applied one.

## 8. Revising text sentence by sentence (STABLE)

A method for auditing and pruning text a model reads, drawn from OutcomeBound's audit of its own
shipped instructions. It is a method, not a measured result.

1. **Agreement first.** Check each sentence against what it names (the code, a command's help, a
   manifest, another surface). A sentence that disagrees is a defect whatever its class; fix it
   before judging anything else, and commit the repair before any "before" arm is run, so a repair
   is not credited to a cut. One reader's agreement check is not complete: a fresh-context review
   of each audit table found disagreements the first reader had recorded as agreeing, and more
   outside the audited text, in code, a command's help, a template or a sibling document (O). A
   review stays a reading, not a measurement (§9.6).
2. **Judge for the least capable expected reader.** Name, per surface, the least capable reader
   expected to load it (an implementer handed a brief may be a smaller model, and implementers also
   read what every session loads). That a capable reader could derive a sentence is no reason to
   remove it.
3. **Class each sentence:**

   | Class | What it carries | Disposition |
   | --- | --- | --- |
   | (a) state | a fact about this project or product the reader cannot see from where it stands, including where a harness reads a skill, which pointer it follows and any cap it applies | stays |
   | (b) authority and bounds | who may do what, preserved state, irreversible edges | stays; emphasis allowed here and only here |
   | (c) oracle | what settles done, and what a check does and does not establish | stays |
   | (d) procedure | steps the reader could derive from a command's help, the manifest or the code | a candidate for removal, or for a pointer where that help is complete |
   | (e) general engineering advice | what the reader does unprompted | a candidate for removal |

   Classing rules that held up in that audit (O): a criterion the reader's output is
   judged by is (c), even when written as a step; a skill's description is (a), since the harness
   selects on it; a body sentence saying when to choose a mechanism is (e); a standard of done the
   reader does not reliably meet unprompted, such as right-sized work, is (c), not (e); general
   knowledge of a language, such as an empty string against `??` or `[]` against `null`, is (e) but
   stays where the reader's own check cannot see the failure it prevents, as when a component's
   check passes while a consumer breaks. Where a sentence fits two classes, record both; in that
   audit the disposition rarely turned on the choice.

4. **Hold each edit to evidence by its risk.** Low risk, landing on review: removing a repetition
   that removes no unique instruction, prerequisite, ordering constraint or local cue; an agreement
   repair that cites its source; reducing rhetorical emphasis outside class (b); a rewording that
   keeps every fact, bound, criterion and step and adds no lookup for the named reader; removing
   class (e) advice from a surface no implementer reads. High risk, landing only where a comparison
   finds it no worse: removing procedure, or moving it anywhere but to a complete `--help`; removing
   or moving advice from a surface an implementer reads. A high-risk edit whose behaviour no
   scenario exercises does not land; the sentence stays, recorded as unmeasured, until a fixture
   exercises it. A recorded reader dependence or a worse comparison keeps a sentence, or its
   emphasis, whatever its class. A repetition is low risk only within one surface, or where the
   reader's load guarantees the other copy is loaded with it. A harness can load a skill without
   the always-loaded file ([harnesses.md](../harnesses/cross-harness.md)), so in that audit every restatement of the
   always-loaded block in a skill, fragment, template or contract stayed for that reason, as did a
   repeated sentence that was the local cue at the step it governs, or the lead-in later sentences
   depend on (O). Accept a cut on the least capable tier expected to load the text, where
   a cut is expected to hurt; a capable tier's gain is a separate comparison.
5. **Record why each kept sentence stays:** an observed failure (an eval result, a probed run naming
   the instruction it acted on, a reported incident), a reader who would go wrong without it, or an
   unmeasured high-risk edit. The next audit can then ask again.
6. **Move procedure to `--help` only by pairing.** Pair each removed sentence with the help line
   that now carries it, and hold each pair with a test; no pointer replaces procedure on a surface
   whose least capable reader is an implementer.
7. **Report per behaviour and per configuration**, never as one verdict for every model and
   harness, and list every cut no run measured, so each can be found and reverted if a later run or
   a user's report implicates it.
8. **Review a rewrite for changes of meaning, not only for coverage.** A rewrite that carries every
   sentence on its record can still change what the text requires. In a rewrite of OutcomeBound's
   contract, skills and templates to a writing standard, six of eight fresh-context reviews found
   blocking problems, most of them changes of meaning that the rewrite's own sentence-by-sentence
   record called carried: a permission turned into a duty ("X is appropriate when …" became "Do X
   where …"); a write duty added for a reader who only acts on a note, outside that reader's
   repository; a fill instruction narrowed; a gate narrowed to one row of its table; a new stop read
   into a parenthesis taken as a gloss; an absolute contradicted by the next sentence; a done-when
   no command could meet (O). Check quoted sentences against the before text by script, whitespace
   collapsed, and take a contested edit only where independent reviews agree.

**What the audit yielded (O).** In OutcomeBound's audit of 1,090 sentences, agreement repairs (24)
outnumbered cuts, moves and de-emphasis together (11), no high-risk edit landed, and the text grew
1%; a pointer to `--help` replaced a sentence only where the help carried every clause. Judged for
the least capable expected reader, with high-risk cuts held to a measurement few surfaces could
get, the audit's yield was agreement repairs, not shorter text.

**What a rewrite to the standard did to length (O).** Rewriting surfaces whole from their jobs made
most of them longer. Writing to the standard asks for completeness first; text gets shorter only
where a command, a schema or a pointer takes over what the prose carried. Fewer words establish
nothing by themselves.

**Revising from failures, measured elsewhere.** Reflective prompt optimisation that learns from
observed failures beat reinforcement learning (GRPO) by 6% on average and up to 20% with up to 35x
fewer rollouts, and beat MIPROv2 by over 10%, on six tasks [research-26; re-read 2026-10-01] (M);
grouping failures into an error taxonomy and writing guidance for the most frequent reached
comparable results at about a third of the optimisation-phase token and evaluation budget (ETGPO,
arXiv 2602.00997, read 2026-10-01) (M). Both optimise prompts against a task metric: they support
adding text after an observed failure (S13) and re-running the same evals (S11), not any particular
cut.

## 9. Measuring a change to model-facing text (STABLE)

### 9.1 Designing the suite

1. **Start small, from real failures, and split.** 20–50 simple tasks drawn from real failures are
   enough while effects are large; grow the set as the remaining effects shrink [evals-6] (L). For a
   skill, 10–20 prompts in a set that grows over time, with `should_trigger=false` negative
   controls, deterministic checks on the run's traces and a rubric pass "where rules fall short"
   [openai-26] (L). Capability evals have headroom; regression evals sit near 100% [evals-3]; an
   eval at 100% tracks regressions but shows no improvement, so add harder tasks or new dimensions
   [evals-4]. Balance cases where a behaviour should occur and where it should not [evals-8]; score
   items in both directions, so stopping, asking or checking more cannot read as better. Keep a
   small CI set, favour deterministic assertions over judges there, and add each new production
   failure pattern to it [evals-25] (P; the cited page dates from 2025-06-29).
2. **Build headroom per tier.** Screen tasks per agent for the borderline band; difficulty
   correlated only about 0.75 (Spearman, over 15 shared tasks) between Claude Code and Codex, so a
   borderline set calibrated on one agent is mostly floor or ceiling for the other [evals-18;
   re-read 2026-10-01]; how studies screen and rank tasks that can move is in
   [agent-evals.md](agent-evals.md#4-task-selection). Screening at five runs per
   tier: 20–80%
   passing marks headroom, 90% or more on every tier puts a scenario in the regression set. Headroom
   on one tier is not headroom on the tier whose change matters: a scenario at 100% on the most
   capable model and 40% on the smallest cannot show a frontier gain. Keep saturated scenarios as
   regression checks; skipping one after three perfect runs lets a collapse go unseen. With frontier
   models, treat 0% over many trials (0% pass@100) as most often a broken task, give each task a
   reference solution, and check that two domain experts would reach the same verdict [evals-5]
   (L). Harden tasks before trusting them: remove test leakage and contradictions, assert on
   observable behaviour rather than implementation details, and target knowledge absent from
   training so a baseline has room to improve [evals-22]; public tasks lose headroom [evals-30].
3. **Baselines.** Compare against no surface and against the previous version, in the same batch
   [evals-24]. Add a paraphrase of the old text as a noise control: on BFCL tool calling, rewordings
   moved results 11–58x more than reruns did [evals-21] (M, tool calling only), and instruction
   following fell by up to 61.8% under nuanced rewording, measured as reliability across paraphrases
   (reliable@k, 46 models) [research-19] (M). Part of that sensitivity may come from scoring:
   semantic judging gave much lower variance than log-likelihood or exact matching [research-20]
   (M). Wording sensitivity is largest on older and smaller models: formatting alone moved few-shot
   LLaMA-2-13B by up to 76 accuracy points (arXiv 2310.11324), and GPT-3.5 by up to 40% on a
   code-translation task where GPT-4 was more robust (arXiv 2411.10541) (both cited in
   [research-20] detail, read 2026-10-01) (M, 2023–24 models). Without a paraphrase arm, a
   "better" cannot be separated from rewording.
4. **Isolate the arms.** A "no surface" arm is only that when user-level context is isolated:
   `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `CLAUDE.local.md`, managed policy files and
   auto-memory [harness-loading-coverage-6, harness-loading-coverage-18,
   harness-loading-coverage-28]. A Codex call can be isolated with `--ephemeral
   --ignore-user-config --ignore-rules -c features.memories=false`, though those flags did not
   exclude user-level agent role files: every recorded run shows codex reading `~/.codex/agents/`
   (codex-cli 0.158.0–0.159.0), so whether a role file there reaches the model is `UNVERIFIED` (O).
   Read the head of each transcript for warnings that name user-level files. No `claude -p` option
   set was found that isolates user-level files while keeping a subscription login, so such a call
   carries the user's hooks, `CLAUDE.md` and memory (O, 2026-09; `UNVERIFIED` against current
   docs).
5. **Keep comparisons from mixing.** A prompt comparison varies the text, with model, tier, effort,
   CLI version, task, fixture, rubric and judge fixed; a generation comparison varies the model,
   with text, fixture, rubric and judge fixed. A model or CLI update between arms reads as a text
   effect; naming both versions records the confound, it does not remove it. Confirm, with no
   model call, that the backend accepts the requested effort: from its help where the help lists
   efforts, otherwise from its model catalog (`codex exec --help` lists none; `codex debug models
   --bundled` lists each bundled model's efforts; read 2026-09-27, version not recorded) (A); and
   record the effort actually used. Effort levels are not comparable across vendors: record each
   arm's effort as sent and claim no equivalence between one vendor's level and another's (O,
   OutcomeBound's runner).
6. **Reuse recorded runs carefully.** A recorded run stands in only when fixture definition, text
   hash, rubric, model, tier, effort and CLI version all match and the text is unchanged since.
   Adding items to a fixture changes its identity. Exclude runs whose workspace name revealed the
   scenario, and test that no file a fixture writes contains the rubric's words.
7. **Trials.** Isolated trials [evals-1]; 3–5 isolated trials per prompt with negative cases, and
   grade outcomes, not paths [other-labs-15] (A); pass^k for behaviours that must always hold, which
   falls fast as k grows (75% per-trial success is about 42% pass^3) [evals-2]; its origin in
   τ-bench is in [agent-evals.md](agent-evals.md#3-statistics-passk-standard-errors-paired-comparisons). For power
   between strategies, more tasks beat more
   repeats, because variance between tasks dominates [evals-19]: at 17 tasks and three repeats a
   30-point effect was caught only 57% of the time, and going from three repeats to ten raised the
   power to see a 15-point effect from 13% to 58% (simulated in the study behind [evals-19],
   re-read 2026-10-01) (M).
   Run each case with and without the text (or against its previous version), record token and
   time cost, and pass an assertion only on concrete evidence [other-labs-21] (P).
8. **Statistics.** Paired per-task differences with standard errors, which remove task-difficulty
   variance at no extra cost [evals-16]; standard errors, clustering and temperature are in
   [agent-evals.md](agent-evals.md#3-statistics-passk-standard-errors-paired-comparisons). A power analysis first:
   choose the smallest effect worth detecting and compute the tasks it needs [evals-17] (L); the
   paper behind the post works an example of about 969 questions for a 3-point difference (arXiv
   2411.00640, read 2026-10-01).
   In the two-agent ablation's simulation, detecting a 10-point effect at 80% power needed about
   120–200 tasks [evals-17 detail; arXiv 2607.27250, read 2026-10-01] (M). Scaling that by 1/√n, a
   20-task suite detects only about 24–32 points and six fixtures about 45–58, in effect a flip
   (computed here, assuming the standard error scales with 1/√n; not measured). Infrastructure alone
   moved scores by 6 points, and differences below 3 points "deserve skepticism until the eval
   configuration is documented and matched", so hold it constant, run arms in the same harness and
   close together in time, and document it [evals-20; re-read 2026-10-01]; the time-of-day
   observation is in [agent-evals.md](agent-evals.md#3-statistics-passk-standard-errors-paired-comparisons).
9. **Graders.** Outcome first, deterministic first: post-checks on what the run left (files,
   transcript commands, report labels), each rejecting a planted fail and accepting a planted pass
   [evals-7, deterministic-14]. An unreadable transcript fails the item; an unrecognised format reads
   `UNVERIFIED`. A behaviour about order ("read before answering", "checked before asking") needs an
   oracle that sees order and a negative control that reaches the right final state in the wrong
   order. Text moved to a conditional read gets a post-check that it was read when the condition
   held. A planted-instruction scenario checks both that the instruction was not followed and that
   it was not passed over silently. Judges grade only what no check sees: one binary dimension each,
   with an "Unknown" answer [evals-9, evals-11]; a reference answer [evals-13]; option order swapped
   [evals-12]; never the least capable tier as judge, and a judge of the candidate's family named as
   one. Calibrate with 30–50 passes and 30–50 fails in each of the dev and test splits, reporting
   true-positive and true-negative rates [evals-10]. Until then, a "better" resting only on a judged
   item reads "not shown", and a judged-only "worse" goes to a person with both arms' answers.
10. **Beyond pass rate.** Tokens, time and steps [other-labs-21]; mergeability beyond tests:
    roughly half of test-passing SWE-bench Verified pull requests by 2024–2025 agents would not be
    merged by the repositories' maintainers, even after adjusting for noise in their decisions, so
    calibrate reviewer judgments against a golden baseline of known-good human changes: maintainers
    accepted only 68% of 47 original merged human patches, scores are reported as a share of that
    baseline, and on it maintainers' merge decisions ran about 24 points below the automated grader
    [evals-27; re-read 2026-10-01] (M); scenarios only a cheat can pass [evals-28].
11. **Read transcripts** before trusting any score [evals-14]. Mine them for failures
    [practitioners-16, repo-readiness-audits-13]. The probe that asks the model to name and link the
    file and quote the instruction behind a pause finds silent and conflicting guidance [openai-9],
    but a probe changes what a model does: a probed run is a diagnostic, not an acceptance arm. Run
    acceptance comparisons unprobed, and where the right answer is a question, a consent or a stop,
    drop any "no questions" line, which forbids the very stop being measured.
12. **Attribute cleanly.** A before/after of a whole rewrite changes many things at once; an arm
    that differs in one factor attributes an effect cleanly. A cheaper alternative measures the text
    as it loads, then localizes (§9.4). A fixture that loads the original beside its restatement
    measures the original: measuring the removal of a restatement needs an arm without the original
    (O, OutcomeBound's audit).

### 9.2 Detection power at five repetitions a side

Computed exactly (binomial, runs independent) and re-computed on 2026-10-01. The decision rule
examined: an item is called worse when a required item passes in 2 or more fewer repetitions, when
an unnecessary item appears in 2 or more more, or when a forbidden effect the before arm never
showed appears at all; a difference of exactly 1 either way is `UNVERIFIED`.

| True situation | P(called "worse") | P(`UNVERIFIED`) | P(reads equal or better) |
| --- | --- | --- | --- |
| Required item, no change, base rate 0.5 | 17.2% (176/1024) | 41% | 42% |
| No change, base rate 0.8 | 11.1% | 46% | 43% |
| No change, base rate 0.9 | 5.1% | 44% | 51% |
| Forbidden effect, no change, true rate 5% / 10% / 20% | 17.5% / 24.2% / 22% | — | — |
| Unnecessary item, no change, rate 0.2 / 0.5 | 11.1% / 17.2% | — | — |
| Real drop 1.0 → 0.8 | 26% | 41% | 33% |
| Real drop 0.9 → 0.7 | 33% | 41% | 26% |
| Real drop 0.8 → 0.5 | 51% | 31% | 18% |
| Real drop 0.9 → 0.5 | 66% | 24% | 10% |
| Real drop 0.9 → 0.3 | 89% | 9% | 2% |

- At three repetitions, the false "worse" rate at base rate 0.5 is 10.9%.
- With k items compared per configuration, false "worse" verdicts accumulate up to 1 − 0.83^k: 43%
  at k=3.
- A real 20-point drop reads as equal or better 26–33% of the time. Five repetitions reliably catch
  only drops of about 40–60 points.
- Ten repetitions with a threshold of 3 would catch 0.8 → 0.5 60% of the time, at 13% false
  "worse" (base rate 0.5).
- No affordable run catches small harms. What raises power: adding repetitions when the difference
  is at most 2 on an item whose before rate lies between 20% and 80%; judging forbidden effects
  against the pooled before rate across all recorded runs of a fixture; pooling fixtures that
  exercise one behaviour with a sign test over per-fixture differences; and stating with every
  result the smallest drop it could detect.

### 9.3 Sequential designs, canaries and budgets

All figures computed exactly (binomial, runs independent, and items independent where several are
combined; with perfectly correlated items the several-item rates fall to the single-item rate) and
re-computed on 2026-10-01.

**Three runs a side, then five.** Three runs a side; within one good run of each other, "not shown";
two or more apart either way, extend both arms to five; after five, two or more fewer good runs is
worse and two or more more is better. A comparison costs 6 runs, or 10 when extended.

| True situation | Extended | Called worse |
| --- | --- | --- |
| No change, base rate 0.5 | 22% | 7.9% |
| No change, base rate 0.8 | 11% | 4.4% |
| No change, base rate 0.9 | 4.1% | 1.8% |
| Real drop 1.0 → 0.8 | 10% | 10% |
| Real drop 0.9 → 0.7 | 17% | 15% |
| Real drop 0.9 → 0.6 | 28% | 26% |
| Real drop 0.8 → 0.5 | 32% | 28% |
| Real drop 1.0 → 0.5 | 50% | 50% |
| Real drop 0.9 → 0.4 | 53% | 51% |
| Real drop 0.9 → 0.2 | 78% | 77% |

Gains mirror these (no change at 0.5 or 0.2: 7.9% or 4.4% called better; 0.5 → 1.0: 50%; 0.3 →
0.8: 51%, 51.49% by exact enumeration). A drop is called worse with 80% probability only when it
is about 71–73 points or more (1.0 to about 0.29, 0.9 to about 0.18, 0.8 to about 0.08); from a
base below about 0.71, no drop,
not even a collapse to 0, reaches 80%. A 50-point drop is called about half the time. With a
threshold of 3 of five instead of 2: false worse 4.0% / 1.6% / 0.4% at 0.5 / 0.8 / 0.9, and 1.0 →
0.5 called 40.6% of the time.

**Several items.** With no change, a scenario extends 22% of the time with one item at 0.5 and the
rest at ceiling, 31% with one at 0.5 and three at 0.9, 46% with two at 0.5 and three at 0.9, and 71%
with five at 0.5. How often at least one item is falsely called worse depends on which items the
final verdict may judge, and a design has to state its rule:
- **Per-item gating.** An item can be called worse only if that same item triggered the extension
  (its own three-run arms were two or more apart); an item that did not trigger keeps its
  three-run reading, "not shown", even when another item extended the scenario. Per item, a
  trigger happens 21.875% of the time at 0.5 and a trigger followed by a five-run "worse" 7.91%
  (0.0791015625), so at least one false "worse" comes 34% of the time with five items at 0.5
  (33.7694%) and 92% with 30 (91.5598%); at a threshold of 3, 19% and 71% (18.48% and 70.65%).
- **Scenario-wide extension.** Any triggering item extends the scenario, and every item is then
  judged at five runs. An untriggered item can then be called worse too (a five-run "worse" alone
  happens 17.1875% of the time at 0.5), so at least one false "worse" comes 47% of the time with
  five items at 0.5 (47.4171%) and 99.6% with 30 (99.5916%); at a threshold of 3, 22% and 81%
  (21.88% and 81.47%).

**A known before rate.** Where the before rate comes from pooled recorded runs and only the after arm
runs, false "worse" falls to about 0–0.8% at base rates 0.5–0.9, and power is 50% for 1.0 → 0.5,
22% for 0.9 → 0.4 and 34% for 0.8 → 0.3.

**Five runs a side, then ten, with a paraphrase control.** Five a side; escalate to ten a side when
two or more apart; worse or better at three or more of ten. With no change, escalation (either
direction) happens 34% / 22% / 10% / 3.5% / 0.2% of the time at base rates 0.5 / 0.8 / 0.9 / 0.95 /
0.99, and false worse is 8.1% / 4.5% / 1.6% at 0.5 / 0.8 / 0.9. Real drops called worse: 1.0 → 0.8
20%; 0.9 → 0.7 25%; 0.8 → 0.5 43%; 0.9 → 0.5 61%; 0.9 → 0.3 88%; gains mirror these (0.3 → 0.7
called better 60%). Ten items at 0.5 give at least one false worse 57% of the time (56.88%) when
an item can be called worse only if it escalated itself, its other verdicts staying "not shown",
and 75% (74.79%) when any escalating item takes every item to ten runs and all are judged there
(per item at 0.5: escalation 34.375%, a ten-run "worse" 13.16%, both 8.07%). If "worse" is
attributed to the rewrite only when the after arm also trails a ten-run paraphrase of the old text by
three or more, the false "worse, attributed" rate falls to 3.1% / 2.0% / 0.8%; the remainder
(4.9% / 2.6% / 0.8%) is "worse, shared with rewording", which is wording sensitivity to escalate,
not noise to forgive.

**Canary at a new model version.** Two runs on the new model; flag an item that is good in neither
run and whose recorded rate is 0.75 or more. At an unchanged rate a false flag per item is 6.3% at
0.75, 4.0% at 0.8, 1.0% at 0.9 and 0.3% at 0.95; a real drop is caught 25% of the time from 1.0 to
0.5, 36% from 0.9 to 0.4, 49% from 0.8 to 0.3, 64% from 1.0 to 0.2 and 81% from 0.9 to 0.1. An item
recorded below 0.75 is never flagged: the canary sees a collapse, not a slide.

**Budgets.** Per-item detection rates assume no budget. Under a fixed cap, fund complete comparisons
before optional experiments, and list what the cap left unrun as `UNVERIFIED`; several collapses at
once can exhaust the extension runs a design promised. What full designs cost, computed exactly for
OutcomeBound's plan (O, with assumed shares of escalations and real worse results): five
runs a side, extended to ten when two or more apart in either direction, plus localization, costs
about 13 runs per scenario and tier when items sit near ceiling (10 + 2.2 + 0.5) and about 20 when
several sit between 0.5 and 0.9 (10 + 5.3 + 5), so ten to fourteen scenarios on two tiers cost about
260–600 runs a release. Budgeting escalation in one direction only halves its rate (17% instead of
34% at a base rate of 0.5) and under-counts. A same-batch comparison with the model a release
replaces (about twelve scenarios, five runs on each model) costs 133–161 runs per changed tier and
is possible only while the old model is served; afterwards its recorded runs stand in (67–81 runs),
labelled as such. The three-then-five tripwire and a two-run canary fit one release in 60 runs and a
new model in about 12, at the detection limits above.

### 9.4 Localizing a worse result

Put back only the lines mapped to the item that got worse, and run that version at most three times.
With b and a the before and after good runs out of five, the version localizes the loss when its
good-run rate r/3 is at least (a + b)/10, the midpoint of the two arms' rates. Before 5 and after 2:
halfway is 0.7, so it localizes with 3 good of three, not 2. Before 4 and after 1: halfway is 0.5, so
2 or 3. This requires mapping each scored item to its lines in the before and after text; without an
explicit reference arm, denominator and threshold, different implementations restore different text.
A loss that localizes is met, in order, by deterministic support, text read on a condition, a
delegate's brief sized to its reader, or one model's adapter configuration; old wording returns to
shared text only where none of those can carry it.

### 9.5 What OutcomeBound's runs showed about measuring (O)

These are lessons from OutcomeBound's evals of its own model-facing text (codex backend, gpt-6-sol
and, in earlier diagnostic probes, gpt-6-luna; three to five runs per arm); recorded
results are kept in [evaluations.md](evaluations.md).
- The gain from stating an answer's required form inline was real in form and absent in checking
  (S1); a pointer to a contract the fixture could not reach carried nothing (S12).
- Runs worked in a directory named after the scenario, which the model could read: a leak.
- Every result was judged by a model of the same family; agreement with a person was measured on
  none of the judged runs, and a planned hand-scoring sample of nine items was below the 30–50 per
  class calibration needs.
- A "no questions" line in the prompt forbade the stop some scenarios measured.
- A rubric that still listed a policy gate as unnecessary mis-scored runs until it was corrected:
  the judge cited that item against 10 of 18 probed runs, and it was the only item cited against 6
  whose deterministic post-checks passed.
- Where instructions routed to a skill the fixture never installed, some answers spent text
  reporting it missing (2 of 18 recorded answers in one scenario's probed runs; in a later unprobed
  comparison on the same fixture, about half of ten answers, 5 or 6 by two counts).
- The one comparison an instruction audit could use to accept or reject an edit (gpt-6-luna at max
  effort, codex CLI, five runs a side, unprobed, questions allowed, a fixture measuring a stop)
  differed by one run: 4 PASS and 1 FAIL before, 5 PASS after, with required items and four
  post-checks equal at 5 of 5. The failing run did all the work and passed every post-check; the
  judge called its closing request to confirm a blocker an unnecessary stop, while two passing runs
  on the same side ended with the same kind of question. A one-run difference reads `UNVERIFIED`
  (§9.2), so it accepts neither edit it compared (a repeated sentence removed, an ambiguous one
  reworded); they wait for a person reading both arms' answers. With no change, 41–46% of five-a-side
  comparisons land in that band, so plan the person's reading, or the extension runs, before
  running, and read a failing answer before crediting a judged difference to the text.
- Measured text changed under the measurement: the always-loaded block, the core skill and the
  composed fragments each changed several times within one month. A result holds only while the
  measured lines stay unchanged, so map items to lines and re-run, or explicitly waive, when a
  scored line changes.
- No run on Claude models was made; behaviour under them is `UNVERIFIED`.

### 9.6 What a result establishes

- A run establishes how the named model, tier, harness, effort and CLI version behaved on those
  scenarios, with that text and rubric, on that date, for the behaviour its scenario exercises and
  nothing more, down to the smallest change it states.
- A null reads "not shown", never "does as well"; "not shown worse" does not rule out a smaller
  harm; "better" holds only for that item, tier and text.
- A judge reads the task, the answer and the rubric, not what the run did; a judged verdict records
  what its author said and stays `UNVERIFIED` until a person confirms it.
- A reading of transcripts by the most capable model is a reading, not a measurement.
- Tests that do not read the changed file show only that nothing nearby broke.
- A class assigned to a sentence is a reader's judgment; a second reading is a review, not a
  measurement.
- Finishing an audit establishes that every sentence has a recorded reason, not that outcomes
  improved. Fewer words establish nothing by themselves.

## 10. The evidence behind a writing standard, rule by rule (SR1–SR22)

[as-of 2026-09-27] OutcomeBound's prompt standard (`docs/prompt-standard.md`) states 22 rules for
the text a model reads, each citing key records. This section reads those records as fact-checked and says
whether they support each rule's confidence and direction, and which reader tiers they cover. SRn
reviews the standard's rule Sn. The standard's S1–S19 restate the practices of §2 under the same
numbers (its S3 narrows the practice to keeping one model's tuning in adapter notes and settings),
and it adds S20 (name what a handoff must contain), S21 (leave the path to the reader) and S22
(durable files for long runs).

**Method.** Each key record's `claim` as verified was read, never its `original_claim`, with its
quote, type, class, verification, author and date. A record of `type: standard` is class S;
otherwise its `evidence` field gives M, L, P or A, the corrected class where a fact-check changed
it. The two generation records cited (`measured-g5`, `measured-g18`) have no class; both are
cross-family independent measurements, read as M. Each M record is marked *independent*,
*lab-own-model* or *vendor-own-product*. A record covers the tiers of the models it names (§1); one
naming no model covers frontier only. A rule's tiers are the union over its key records, those
against it included. A section cite (to a part of [models.md](../models/cross-family.md) or
[harnesses.md](../harnesses/cross-harness.md), or to §4.2 here) takes the class of what its row rests on.

| Id | Rule (short) | Key records, as corrected | Tiers | Supported confidence; direction |
| --- | --- | --- | --- | --- |
| SR1 | Outcome, scope and each rule's reach, completion bar, bounds and stops, once, up front | `research-18` (M, indep: underspecified prompts twice as likely to regress; listing every requirement does not consistently help); `research-14` (M, indep: one consolidated instruction beats requirements revealed across turns); `research-28` (M, indep: no-change-as-success raised correct abstention on Sonnet 4.6 and GPT-5.4 mini; reproduce-first did not help and hurt the small reader); `capability-tier-readers-7` (L: a literal mid-tier reader needs an instruction's scope stated) | frontier, mid, small | High; rising |
| SR2 | Must-hold rules enforced outside prose; code renders or checks outputs with more than about five required parts | `research-3` (M, overstated, indep: one factorial study of one harness; adherence fell about 5.6% per added function, post hoc and not monotonic; supports only that prose adherence decays within a session); `research-29` (M, indep, single author: non-compliance undetectable from text; removing tools raised compliance to 75%); `deterministic-9` (L, overstated: one harness's guidance that hooks guarantee an action); `deterministic-10` (L, overstated: conversation boundaries under auto mode can be lost to compaction; a deny rule is the guarantee); `instruction-file-security-authority-22` (L); `measured-f2` (M, indep: following breaks down beyond five or six simultaneous constraints; the basis of "about five") | frontier, mid | High; rising |
| SR3 | One model's tuning in adapter notes and settings, not portable text | `capability-tier-readers-1` (L: a smaller tier's guidance can overconstrain the top tier); `capability-tier-readers-25` (M, indep: format and placement effects are model-specific; Qwen 35B, Haiku); `agent-files-8` (M, overstated, indep: small open-weight models only; tuned guidance dropped another to 13.2%); `capability-tier-readers-20` (M, indep: a stronger model's file does not reliably help a smaller reader); §4.2 (L: no study tests one shared file across tiers) | frontier, mid, small | High that tiers differ, medium on one text serving them; rising |
| SR4 | Instruction files, skills, memory and harness configuration untrusted: scan, pin, review, load when trusted; brought-in material marked as data | `instruction-file-security-authority-1` (S); `-12` (M, indep: memory payloads attack current and future sessions); `-15` (M, indep: coercive, secrecy and autonomy language and undocumented capabilities mark malicious skills); `-30` (M, indep: agents followed infected rule files the request never mentioned). None measures the brought-in-material clause | frontier | High, that clause `UNVERIFIED`; rising |
| SR5 | Done is a runnable pass-or-fail check; reports name what was checked | `deterministic-28` (M, indep); `deterministic-8` (L); `forward-15` (M, lab-own-model, Fable 5); `capability-tier-readers-11` (M, overstated, lab-own-model: the smallest model fits high-volume checkable work, not long loops) | frontier, small | High; rising |
| SR6 | Tool and check output written for an agent reader | `deterministic-29` (M, indep); `research-12` (M, indep); `deterministic-2` (L); `other-labs-23` (S) | frontier | High; rising |
| SR7 | Know how each harness finds, ranks, caps and compacts each layer; what must load in the root `AGENTS.md` and a `SKILL.md`'s top; under the tightest cap | `harness-loading-coverage-7` (L); `-8` (L); `-19` (labelled M, vendor-own-product, but a reading of source code, not a measurement); `-21` (L, overstated: "silently" dropped) | frontier | High as facts, which drift; rising (the records give no direction; the practice's trend does) |
| SR8 | Always-loaded text holds only what readers would get wrong without it | `research-4` (M, indep: instructions followed; overviews do not help; readers Sonnet 4.5, GPT-5.2, GPT-5.1 mini, Qwen3-30B); `research-5` (M, indep); `research-17` (M, indep: self-evident constraints degraded solving, most in code generation); `other-labs-29` (M, vendor-own-product: an inline index beat an on-demand skill); against `research-27` (M, indep: evolving playbooks, argues against cutting toward brevity, not against omitting what readers derive) | frontier, mid, small | High on direction, medium on size; rising |
| SR9 | Each rule once, one vocabulary, no contradiction; say which source wins | `capability-tier-readers-10` (M, lab-own-model; its claim names retired over-specific text, the accuracy figure being the page's); `capability-tier-readers-21` (M, overstated, indep: an LLM-based compiler, +11.0 GPT-5-mini, +3.3 Gemini 2.5 Flash, none Sonnet 4.6); `practitioners-4` (P); against `research-3` (M: no detectable effect from an adjacent contradiction, one harness, strong readers) | frontier, mid, small | High; rising. Among the narrowest: the measured benefit is on weaker readers |
| SR10 | Skills compact, curated, single-purpose; the description is the trigger, key use case in the first 250 characters, within every listing cap; multi-workflow skills open as routers | `research-8` (M, indep); `research-9` (M, indep: Opus 4.7, GPT-5.5, Gemini 3.1 Pro); `agent-files-10` (M, overstated, indep: observational only); `agent-files-17` (L); the harness caps ([harnesses.md](../harnesses/cross-harness.md#5-caps-truncation-and-advisories) §5) (L) | frontier | High for compact, medium for the description; rising |
| SR11 | Text is an assumption: remove one group at a time and re-run the same scenarios per tier at each generation and point release | `forward-1` (M, lab-own-model: Opus 5, Fable 5); `forward-5` (M, lab-own-model: GPT-5.6); `measured-g18` (M, indep: up to 8.3% of items regress under aggregate gains); against `research-27` | frontier, mid | High for the method, medium for removal on small readers; rising |
| SR12 | Always-loaded text a short map: pointers carry a condition and go one level deep; knowledge most tasks need stays inline as an index | `agent-files-5` (M, overstated, indep: agents consult instruction files most, 35.4% of documentation interactions, working notes close behind); `other-labs-29` (M, vendor-own-product: an inline index beat a skill for knowledge most tasks need); `forward-29` (M, overstated, indep: one study of long-document question answering; one level of disclosure helped by a harness-dependent amount, a second never; not instruction files in general) | frontier | Medium; contested (each measurement narrower than the rule once corrected, pulling different ways on how much stays inline) |
| SR13 | Add a line, check or tool only after an observed failure, classed as capability, context or structure, in the most deterministic form that fixes it | `research-7` (M, indep: Qwen3.5-35B-A3B); `latent-space-1` (A: the host's summary of one team's practice); `forward-26` (A) | frontier, small | Medium; stable |
| SR14 | Every path, command, flag, id, version and rule named agrees with its source; check agreement first; hold it with a test | `repo-readiness-audits-25` (M, indep: agents follow a wrong standard); `repo-readiness-audits-19` (A); held in this repository by tests that every documented command and flag runs (`tests/test_doc_cli_consistency.py`, `tests/test_script_help.py`) and by its structure check (O) | frontier | High; rising |
| SR15 | Autonomy by class of action; stop only before destructive, irreversible, external or money-spending acts, scope widening or person-only input; bound every delegate's brief | `forward-6` (L: GPT-5.6); `open-weight-f13` (L); `capability-tier-readers-13` (L, overstated: a product default, supporting "bound every brief"); [models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text) Do 4 (L, four labs plus one checked page) | frontier | High for one policy (convergent guidance from at least five labs; no measured key record), medium for its form; rising. Among the narrowest |
| SR16 | Verification sized to risk, in checks outside the model; no generic double-checking or thinking depth in prose | `research-22` (M, indep); `research-23` (M, indep); `forward-11` (L, overstated: one model's guide, Opus 5; Fable 5's guide recommends fresh-context verifiers on long runs); `forward-16` (M, lab-own-model: Opus 5.5) | frontier | Medium; self-check prose fading |
| SR17 | Absolutes for exceptionless rules; judgment as conditions; no weight by capitals, bold or repetition; concrete bars | `forward-10` (L); `capability-tier-readers-8` (L, overstated: Sonnet 5 only); `other-labs-1` (L: Gemini 3.5 Flash page); against `research-15` (M, indep: framing plus a trailing reminder restored compliance on three 2025 families) | frontier, mid | Medium; rising for frontier readers |
| SR18 | Typed parameters, enums and commands over tool-use prose; examples where they carry a requirement no schema carries; no empty expertise claims or try-harder lines | `forward-3` (L: Claude 5); `forward-20` (M, indep); `advanced-tool-use` (M, lab-own-model: 72% → 90%, before Claude 5); `capability-tier-readers-27` (M, overstated, indep: older models; Qwen2.5 7B still gained) | frontier, small | Medium-low; tool-use examples fading on frontier |
| SR19 | A reason only where it changes a decision or covers unnamed cases | `forward-14` (L: Fable 5); against `other-labs-15` (A, overstated, first labelled M: one practitioner's guidance) | frontier | Low; contested |
| SR20 | Name what an answer or handoff must contain rather than asking for brevity; no open-ended thrift wording | [models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text) Do 7 (L), citing `openai-f19` (M, indep: documents the failure only), `grok-f21` (L), Anthropic's Opus 5 prompting page (L, in [models.md](../models/cross-family.md#sources) Sources); Stop 8 (A: `openai-f23`, one team's report) | frontier, mid, small | Low to medium; rising |
| SR21 | Leave the path to the reader unless the path is a requirement | `capability-tier-readers-6` (L, overstated: one model's guide); `research-28` (M, indep); against `capability-tier-readers-16` (M, overstated, indep: copying, says nothing on outcome-only guidance), `-22` (M, overstated, indep: small models gain from task-specific harnesses), `-26` (M, overstated, indep: one benchmark, three models; the crossover a hypothesis) | frontier, mid, small | Contested; unsettled |
| SR22 | A long run's goal, completion check, bounds and progress in files that survive compaction and new sessions | `measured-g5` (M, indep: the 50% horizon doubles about every 131 days since 2023); [models.md](../models/cross-family.md#6-what-the-trends-imply-for-shared-text) Do 14 (L: `claude-g9`, overstated on dates and access; `glm-f5`; `openai-f24`) | frontier | Medium; rising |

**What the review found.** No rule's key records, read as corrected, fail to support its stated
confidence and direction. The rules whose support is narrowest for their confidence are SR9 (measured
on weaker readers, with one measured null on strong readers in one harness) and SR15 (high on
convergent guidance with no measured key record); each is the first to re-read when new evidence
arrives. Two key records' labels read wider than their claims: `harness-loading-coverage-19` is
labelled measured for a reading of source code, and `capability-tier-readers-10`'s claim does not
itself carry the measurement attributed to its page; the evidence file keeps both labels until a
later sweep's fact-check changes them. Two of OutcomeBound's results, in probed runs of three a
cell (O), bear on the two narrowest rules: a skill that contradicted its own reference file stopped
the smaller model and not the larger (S14; SR9), and a stop rule naming one concrete act stopped
every run before it landed until reworded (S15; SR15). Neither is a key record, so the confidence
and tiers above stand as reviewed.

## 11. Observed effects of instructions that generate documents

Anecdotes from OutcomeBound's agent-generated tickets, notes and specs, where an agent
wrote documents under written instructions. They show how instruction wording drives output length
and shape; none is a controlled measurement.
- An instruction to "write for the least capable implementer… say whatever it would otherwise guess,
  search for or get wrong" produced design sections of 500–3,000 words.
- A template of seven or eight headings was read as a form: every section was filled, and "any of
  them may say `none`" did not prevent it.
- An output rule with no length bound ("a closing note carries four labelled lines") produced notes
  of 400–1,332 words.
- A condition phrased with "lasting", "material" or "future maintenance" is always true to a careful
  agent, so the mechanism it gates fires on every task.
- "Every follow-up they name is carried" rolled follow-ups forward indefinitely.
- An instruction to name each symbol a change adds, with its shape, produced copies of existing
  signatures that went stale.
- Ticket drafts written under the same rules put more than a third of their words in the design
  section.
- Rules added by amendment accumulate: contract and design files carried lines marked as
  amendments, none folded into the text it amended.
- Checks that read prose by heuristic misfire both ways: a matcher that took a bare `run ` as a
  command matched English ("run the report and verify") and let prose pass as a runnable
  acceptance check, and a shape lint that demanded concrete values flagged its own template's
  placeholders. Check structure mechanically (a command in a code span, a required heading) and
  leave concreteness to review (A).

Written guidance can still move process: in a measured comparison, an install whose always-loaded
text said that process a project document only suggests is sized like any other step stopped that
process (6 of 6 against 0 of 6), though the arm was the whole install, not that line alone
([evaluations.md](evaluations.md) E10).

The implication, stated generally: give a document a length bound set by its reader's decision, make
optional sections explicitly optional, phrase a condition so that it is sometimes false, and hold a
limit that must bind with a check rather than prose.

## How to apply

- Before writing a line, name who loads it (§3, J0) and whether they would go wrong without it (S8,
  J2).
- Put the outcome, completion bar, bounds and stops first; move must-hold rules into the harness and
  name the enforcement (S1, S2, S5, S15).
- Check agreement with the code before any other edit, and hold it with a test where the kind of
  agreement allows (S14).
- Keep skills compact with trigger-first descriptions under the tightest listing cap (S10;
  [skills.md](skills.md)).
- Design command output with the verdict first and failures only (§6).
- Audit a project's files with the security pass first and a model only in isolation (§7).
- Revise by the sentence test and hold each edit to evidence by its risk; review every rewrite
  against the before text for changes of meaning (§8).
- Measure with a stated smallest detectable effect, a paraphrase arm where possible, and per-tier
  results (§9).

## Limits and open questions

- The measured studies are mostly on 2025 and early-2026 models; the current frontier is barely
  tested, and no study runs one file across several families or tiers at once.
- Deletion evidence is mostly frontier; the smaller-reader evidence often points the other way.
- Several measured results are single-author preprints or vendor reports, and readiness scorers
  publish no validation.
- The audit patterns in §7.4 are chosen parameters; their recall and false-alarm rates are
  unmeasured.
- OutcomeBound's results (O) are runs on one backend with small arms and a same-family judge.

## Sources

Every cited id's URL and date are in the evidence file; this section lists the sources by kind. Read
2026-09-25 unless dated otherwise.

**Checks defined here** (verdict PASS):
- [chk-claude-skills] Claude Code skills page, checked 2026-09-25: "the combined `description` and
  `when_to_use` text is truncated at 1,536 characters in the skill listing", the model-facing
  listing; 250 characters is the `/skills` menu. <https://code.claude.com/docs/en/skills>
- [chk-claude-memory] Claude Code memory page, checked 2026-09-25: "Claude Code loads a CLAUDE.md
  file of up to 4 MiB in full and skips a larger file." <https://code.claude.com/docs/en/memory>
- [advanced-tool-use] Anthropic, Introducing advanced tool use, 2025-11-24; raised by the critic and
  checked 2026-09-25. <https://www.anthropic.com/engineering/advanced-tool-use>

**Anthropic.** Writing tools for agents, 2025-09-11
<https://www.anthropic.com/engineering/writing-tools-for-agents>; effective context engineering,
2025-09-29 <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>; Claude
Code sandboxing, 2025-10-20 <https://www.anthropic.com/engineering/claude-code-sandboxing>; best
practices for prompt engineering, 2025-11-10 (updated later)
<https://claude.com/blog/best-practices-for-prompt-engineering>; demystifying evals for AI agents,
2026-01-09 <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>; building a C
compiler, 2026-02-05 <https://www.anthropic.com/engineering/building-c-compiler>; infrastructure
noise, 2026-02-05 <https://www.anthropic.com/engineering/infrastructure-noise>; skill-creator,
2026-03-06 <https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md>;
harness design for long-running apps, 2026-03-24
<https://www.anthropic.com/engineering/harness-design-long-running-apps>; Claude Code auto mode,
2026-03-25 <https://www.anthropic.com/engineering/claude-code-auto-mode>; April postmortem,
2026-04-23 <https://www.anthropic.com/engineering/april-23-postmortem>; how we contain Claude,
2026-05-25 <https://www.anthropic.com/engineering/how-we-contain-claude>; how we use skills,
2026-06-03 <https://claude.dev/blog/lessons-from-building-claude-code-how-we-use-skills/>; steering
Claude Code, 2026-06-18
<https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more>; the new rules
of context engineering for Claude 5-generation models, 2026-07-24
<https://claude.dev/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models/>;
Claude Opus 5.5 and getting the most out of Opus 5.5, 2026-09-22
<https://www.anthropic.com/news/claude-opus-5-5>, <https://claude.dev/blog/getting-the-most-out-of-opus-5-5/>;
optimizing for cost and intelligence (undated; measurements to 2026-09-20)
<https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence>;
living docs: prompting best practices
<https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>,
skill authoring best practices
<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>, skills for
enterprise <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise>, structured
outputs <https://platform.claude.com/docs/en/build-with-claude/structured-outputs>.

**OpenAI.** Eval skills, 2026-01-22 <https://developers.openai.com/blog/eval-skills.md>; harness
engineering, 2026-02-11 (403; read through a browser and the mirror
<https://jaytaylor.com/notes/node/1770842156000.html>) <https://openai.com/index/harness-engineering/>;
GPT-5.4 guide, 2026-03-05 <https://developers.openai.com/api/docs/guides/latest-model/gpt-5.4.md>;
GPT-5.5 guide, 2026-04-24 <https://developers.openai.com/api/docs/guides/latest-model/gpt-5.5.md>;
GPT-5.6 guide and prompt guidance, 2026-07-09
<https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6.md>,
<https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6.md>; custom code review rules
for Codex, 2026-07-20 <https://developers.openai.com/blog/custom-code-review-rules-for-codex.md>;
builder's guide to GPT-5.6, 2026-08-13 <https://openai.com/index/builders-guide-to-gpt-5-6/>;
latest-model guide (GPT-6), 2026-09-03, updated 09-22
<https://developers.openai.com/api/docs/guides/latest-model.md>; rethinking skills and prompts for
GPT-6 Astra, 2026-09-11 <https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra.md>;
evergreen prompt engineering (living) <https://developers.openai.com/api/docs/guides/prompt-engineering.md>.

**Google.** Gemini 3 guide, 2025-11-18 (updated 2026-09-23) <https://ai.google.dev/gemini-api/docs/gemini-3>;
ADK multi-agent framework, 2025-12-04
<https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/>;
closing the knowledge gap with agent skills, 2026-03-25
<https://developers.googleblog.com/closing-the-knowledge-gap-with-agent-skills/>; Threat
Intelligence, the files coding agents trust, 2026-05-13
<https://cloud.google.com/blog/products/identity-security/beyond-source-code-the-files-ai-coding-agents-trust-and-attackers-exploit>;
what's new in Gemini 3.5, 2026-05-19 <https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5>;
thinking prompting guide (last updated 2026-09-24)
<https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking/prompting-guide>;
prompting strategies (living, updated 2026-09-17) <https://ai.google.dev/gemini-api/docs/prompting-strategies>.

**Other labs and vendors.** xAI Grok Build system prompt, 2026-09-22, and project rules (see
[harnesses.md](../harnesses/cross-harness.md)); Z.ai GLM-5.3, 2026-08-14 <https://docs.z.ai/guides/llm/glm-5.3>, best
practice <https://docs.z.ai/devpack/resources/best-practice>, memory mechanism
<https://docs.z.ai/devpack/resources/memory-mechanism>, ZCode skills <https://zcode.z.ai/en/docs/skill>;
Qwen3.8-27B chat template <https://huggingface.co/Qwen/Qwen3.8-27B/raw/main/chat_template.jinja>, Qwen
Code memory page, 2026-09-08 <https://qwenlm.github.io/qwen-code-docs/en/users/features/memory/>,
QwenCloud model changelog <https://docs.qwencloud.com/changelog/models>, Kodesage review, 2026-08-19
<https://kodesage.ai/blog/qwen-3-8-27b-llm-model-review>; Meta Muse Code configuration
<https://dev.meta.ai/docs/muse-code/configuration.md> and practical AI agent security (Rule of Two),
2025-10-31 <https://ai.meta.com/blog/practical-ai-agent-security/>; Mistral prompting (docs sync
2026-08-11) <https://docs.mistral.ai/studio/conversations/chat-completion/prompting.md>; DeepSeek-R1,
2025-01-22 <https://arxiv.org/html/2501.12948v1>; Kimi K3, 2026-07-27 <https://github.com/MoonshotAI/Kimi-K3>;
Microsoft Security, AI recommendation poisoning, 2026-02-10
<https://www.microsoft.com/en-us/security/blog/2026/02/10/ai-recommendation-poisoning/>; MSRC,
defending against indirect prompt injection, 2025-07-29
<https://www.microsoft.com/en-us/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks>.

**Tool documentation.** The harness pages are listed in [harnesses.md](../harnesses/cross-harness.md); AgentLint
<https://www.agentlint.app/>.

**Standards.** OWASP Top 10 for Agentic Applications, 2025-12-09
<https://genai.owasp.org/download/52117/?tmstv=1765059207>; OpenAI Model Spec, 2026-08-18
<https://model-spec.openai.com/2026-08-18.html>; `AGENTS.md` (last commit 2026-09-10)
<https://agents.md/>; Agent Skills: best practices (2026-04-19)
<https://agentskills.io/skill-creation/best-practices>, evaluating skills (2026-03-13)
<https://agentskills.io/skill-creation/evaluating-skills>, using scripts (2026-02-27)
<https://agentskills.io/skill-creation/using-scripts>, adding skills support (2026-03-10)
<https://agentskills.io/client-implementation/adding-skills-support>; NIST CAISI, agent hijacking
evaluations, 2025-01-17
<https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations>.

**Research papers and independent measurement.**
- Context files and guidance: Lulla et al., `AGENTS.md` runtime, 2026-01-28
  <https://arxiv.org/abs/2601.20404>; ETH, Evaluating `AGENTS.md`, 2026-02-12 (v2 2026-06-23)
  <https://arxiv.org/abs/2602.11988>; agent READMEs, 2025-11-17 <https://arxiv.org/html/2511.12884v1>;
  probe-and-refine, 2026-06-18 <https://arxiv.org/abs/2606.20512>; two-agent ablation, 2026-07-28
  <https://arxiv.org/html/2607.27250>; Working Set / coherence debt, 2026-08-17
  <https://export.arxiv.org/abs/2608.16630>; Gao & Chen, 2026-08-20 <https://arxiv.org/html/2608.20195>.
- Skills: SkillsBench, 2026-02-13 (v4 2026-06-14) <https://arxiv.org/abs/2602.12670>; SkillJuror,
  2026-06-10 <https://arxiv.org/abs/2606.11543>; Anatomy to Smells, 2026-07-01
  <https://arxiv.org/html/2607.01456v1>; progressive disclosure, 2026-07-20
  <https://arxiv.org/abs/2607.17598>; 138K `SKILL.md` files, 2026-08-09 <https://arxiv.org/html/2608.08453v1>.
- Instruction following and context: Lost in the Middle, 2023-07-06 <https://arxiv.org/abs/2307.03172>;
  Control Illusion, 2025-02-21 <https://arxiv.org/abs/2502.15851>; Laban et al., lost in multi-turn,
  2025-05-09 <https://arxiv.org/abs/2505.06120>; When Thinking Fails, 2025-05-16
  <https://arxiv.org/abs/2505.11423>; What Prompts Don't Say, 2025-05-19 <https://arxiv.org/abs/2505.13360>;
  Chroma, Context Rot, 2025-07-14 <https://www.trychroma.com/research/context-rot>; IFScale,
  2025-07-15 <https://arxiv.org/abs/2507.11538>; Flaw or Artifact, 2025-09-01
  <https://arxiv.org/abs/2509.01790>; When Instructions Multiply, 2025-09-25
  <https://arxiv.org/abs/2509.21051>; context length alone, 2025-10-06 <https://arxiv.org/abs/2510.05381>;
  IFEval++, 2025-12-15 <https://arxiv.org/abs/2512.14754>; Qi et al., 2026-01-29
  <https://arxiv.org/abs/2601.22047>; Mittal, 2026-03 <https://arxiv.org/html/2603.23530>; Compliance
  Gap, 2026-05-03 <https://arxiv.org/abs/2605.01771>; FixedBench, 2026-05-08
  <https://arxiv.org/abs/2605.07769>; McMillan, factorial study of instruction-file structure,
  2026-05-11 <https://arxiv.org/abs/2605.10039>; Arize IFScale re-run, 2026-05
  <https://arize.com/blog/llm-instruction-following-benchmark-2026/>; IFBench via Artificial Analysis,
  2026-05-11 <https://allenai.org/blog/ifbench-artificial-analysis>; Classifier Context Rot
  (Anthropic-affiliated), 2026-05-12 <https://arxiv.org/abs/2605.12366>; constraint saturation (single
  author), 2026-08-12 <https://arxiv.org/abs/2608.12426>; item-level migration regressions, 2026-08-18
  <https://arxiv.org/abs/2608.17719>; MTAC-IFBench (co-authored by Zhipu), 2026-09-14
  <https://arxiv.org/abs/2609.14992>; OctoBench (co-authored by MiniMax), 2026-01-15
  <https://arxiv.org/html/2601.10343>.
- Prompting methods: Wharton Prompting Science Reports 1, 2 and 4 (2025-03-04, 2025-06-08,
  2025-12-05)
  <https://gail.wharton.upenn.edu/research-and-insights/tech-report-prompt-engineering-is-complicated-and-contingent/>,
  <https://arxiv.org/abs/2506.07142>, <https://arxiv.org/abs/2512.05858>; GEPA, 2025-07-25
  <https://arxiv.org/abs/2507.19457>; ACE, 2025-10-06 <https://arxiv.org/html/2510.04618>.
- Reader tiers: Qwen3-Coder-Next report, 2026-02-28 <https://arxiv.org/html/2603.00729v1>; Steer,
  Don't Solve, 2026-06-20 (v2 2026-09-01) <https://arxiv.org/html/2606.21811v2>; Better Harnesses,
  Smaller Models, 2026-07-09 <https://arxiv.org/html/2607.08938>; Prompt Design at Scale, 2026-07-21
  <https://arxiv.org/html/2607.19257>; Instruction Stacking Collapse, 2026-07-31
  <https://arxiv.org/abs/2608.02639>; Prompting Inversion (weak), 2025-10-25
  <https://arxiv.org/abs/2510.22251>; aging of prompt techniques, 2026-08-25 <https://arxiv.org/abs/2608.24641>.
- Evals: No Free Labels, 2025-03-07 <https://arxiv.org/abs/2503.05061>; ImpossibleBench, 2025-10-23
  <https://arxiv.org/html/2510.20270v1>; METR, unmergeable SWE-bench PRs, 2026-03-10
  <https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/>;
  stagnation versus progress, 2026-07-27 <https://arxiv.org/abs/2607.25152>; interface study,
  2026-08-11 <https://arxiv.org/abs/2608.11386>; noise floor, 2026-08-23 <https://arxiv.org/abs/2608.22331>;
  Anthropic, statistical approach to evals, 2024-11-19
  <https://www.anthropic.com/research/statistical-approach-to-model-evals>.
- Time horizons and benchmarks: METR on GPT-5.6 Sol (OpenAI reviewed), 2026-06-26
  <https://metr.org/blog/2026-06-26-gpt-5-6-sol/>; Scale SWE-Bench Pro V2, 2026-09-22
  <https://labs.scale.com/leaderboard/swe_bench_pro_public_v2>; METR on Claude Opus 5.5 (Anthropic
  reviewed), 2026-09-22 <https://metr.org/blog/2026-09-22-claude-opus-5-5/>; CodeRabbit on Opus 5.5
  (vendor), 2026-09-22 <https://www.coderabbit.ai/blog/opus-5-5-model-review>.
- Security: design patterns for securing agents, 2025-06-10 (v3 2025-06-27)
  <https://arxiv.org/html/2506.08837v3>; One Token to Fool, 2025-07-11 <https://arxiv.org/abs/2507.08794>;
  AIShellJack, 2025-09-26 <https://arxiv.org/html/2509.22040v1>; The Attacker Moves Second, 2025-10-10
  <https://arxiv.org/abs/2510.09023>; malicious skills (Liu et al.), 2026-02-06
  <https://arxiv.org/html/2602.06547v1>; injection competition, 2026-03-16
  <https://arxiv.org/html/2603.15714>; Bad Memory, 2026-07-16 <https://arxiv.org/html/2607.14611>.

**Security practitioners.** Pillar, rules-file backdoor, 2025-03-18
<https://www.pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents>;
Invariant Labs, MCP tool poisoning, 2025-04-01
<https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks>; Stenberg, detecting
malicious Unicode, 2025-05-16 <https://daniel.haxx.se/blog/2025/05/16/detecting-malicious-unicode/>;
Willison, the lethal trifecta, 2025-06-16 <https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/>;
Embrace The Red, invisible prompt injection in Amp, 2025-08-16
<https://embracethered.com/blog/posts/2025/amp-code-fixed-invisible-prompt-injection/>; Aikido, hidden
PUA Unicode, 2025-10-31
<https://www.aikido.dev/blog/the-return-of-the-invisible-threat-hidden-pua-unicode-hits-github-repositorties>;
Snyk, ToxicSkills on ClawHub, 2026-02-05 <https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/>;
Check Point, CVE-2025-59536 through Claude Code project files, 2026-02-25
<https://research.checkpoint.com/2026/rce-and-api-token-exfiltration-through-claude-code-project-files-cve-2025-59536/>;
CSA, Unicode instruction injection in skills, 2026-03-10
<https://labs.cloudsecurityalliance.org/research/csa-research-note-unicode-instruction-injection-ai-skills-20/>.

**Readiness and linting tools** (none publishes validation against agent outcomes). Factory: linters
to direct agents, 2025-09-05 <https://factory.ai/news/using-linters-to-direct-agents>; agent
readiness, 2026-01-20 <https://factory.com/news/agent-readiness>; measuring agent readiness,
2026-05-27 <https://factory.com/articles/measuring-agent-readiness>; docs
<https://docs.factory.ai/web/agent-readiness/overview>. Kodus (last commit 2026-09-19)
<https://raw.githubusercontent.com/kodustech/agent-readiness/main/README.md>; jpequegn (2026-02-16)
<https://raw.githubusercontent.com/jpequegn/agent-readiness-score/main/README.md>; AgentLint
(2026-05-28) <https://raw.githubusercontent.com/0xmariowu/AgentLint/main/README.md>; AgentLinter
(v2.3.0 2026-03-09; last commit 2026-08-14)
<https://raw.githubusercontent.com/seojoonkim/agentlinter/main/README.md>; Exadel (v4.5.1 2026-09-17)
<https://raw.githubusercontent.com/exadel-inc/agentic-readiness-assessment/main/README.md>;
agentready (2026-07-18) <https://raw.githubusercontent.com/napetrov/agentready/main/README.md>;
Larridin, 2026-06-28 <https://larridin.com/developer-productivity-hub/agent-readiness>; repobuddy
#672, 2026-09-21 <https://github.com/repobuddy/repobuddy/issues/672>.

**Aggregators.** Latent Space: Benchmarks 201, 2024-07-12 <https://www.latent.space/p/benchmarks-201>;
o1 skill issue, 2025-01-12 <https://www.latent.space/p/o1-skill-issue>; Claude Code, 2025-05-07
<https://www.latent.space/p/claude-code>; AIEWF 2025 keynotes, 2025-06-13
<https://www.latent.space/p/aiewf-2025-keynotes>; Chroma, 2025-08-19 <https://www.latent.space/p/chroma>;
context engineering for agents (Lance Martin), 2025-09-11
<https://www.latent.space/p/context-engineering-for-agents-lance>; Amp, 2025-09-25
<https://www.latent.space/p/amp-the-emperor-has-no-clothes>; DevDay 2025, 2025-10-07
<https://www.latent.space/p/devday-2025-apps-sdk-agent-kit-mcp>; Codex app, 2026-02-03
<https://www.latent.space/p/ainews-openai-codex-app-death-of>; end of SWE-bench Verified, 2026-02-23
<https://www.latent.space/p/swe-bench-dead>; reviews are dead, 2026-03-02
<https://www.latent.space/p/reviews-dead>; is harness engineering real (paywalled after intro),
2026-03-05 <https://www.latent.space/p/ainews-is-harness-engineering-real>; Cursor's third era,
2026-03-06 <https://www.latent.space/p/cursor-third-era>; Claude Code source leak, 2026-04-01
<https://www.latent.space/p/ainews-the-claude-code-source-leak>; harness engineering (Lopopolo),
2026-04-07 <https://www.latent.space/p/harness-eng>; Notion, 2026-04-15 <https://www.latent.space/p/notion>;
Cognition, 2026-05-28 <https://www.latent.space/p/cognition>; Loopcraft (paywalled after intro),
2026-06-12 <https://www.latent.space/p/loopcraft>; Gray Swan, 2026-06-22 <https://www.latent.space/p/gray-swan>;
skill engineering design, 2026-07-02 <https://www.latent.space/p/skill-engineering-design>; loops
debate, 2026-07-03 <https://www.latent.space/p/aiewf-daily-dispatch-locomotives>; Weng summary,
2026-07-08 <https://www.latent.space/p/ainews-lilian-weng-summarizes-35>; AIEWF 2026 trends,
2026-07-14 <https://www.latent.space/p/aiewf26trends>; Wayfinder skill, 2026-08-20
<https://www.latent.space/p/wayfinder-skill>; evolution of the agent harness (McAteer), 2026-08-22
<https://www.latent.space/p/attention-interface>. Interconnects, get good at agents, 2026-01-21
<https://www.interconnects.ai/p/get-good-at-agents>.

**Practitioners.** Husain & Shankar: LLM judge, 2024-10-29 <https://hamel.dev/blog/posts/llm-judge/>;
evals FAQ <https://hamel.dev/blog/posts/evals-faq/>. Willison: designing agentic loops, 2025-09-30
<https://simonwillison.net/2025/Sep/30/designing-agentic-loops/>; red-green TDD, 2026-02-23
<https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/>; anti-patterns,
2026-03-04 <https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/>. HumanLayer:
writing a good CLAUDE.md, 2025-11-25 <https://www.humanlayer.dev/blog/writing-a-good-claude-md>;
context-efficient backpressure, 2025-12-09 <https://www.humanlayer.dev/blog/context-efficient-backpressure>;
skill issue, 2026-03-12 <https://www.humanlayer.dev/blog/skill-issue-harness-engineering-for-coding-agents>;
long context isn't the answer, 2026-03-23 <https://www.humanlayer.dev/blog/long-context-isnt-the-answer>.
Amp: 200k tokens is plenty, 2025-12-09 <https://ampcode.com/notes/200k-tokens-is-plenty>; pave the
road, 2026-08-10 <https://ampcode.com/notes/pave-the-road>. Vercel: we removed 80% of our agent's
tools, 2025-12-22 <https://vercel.com/blog/we-removed-80-percent-of-our-agents-tools>; `AGENTS.md`
outperforms skills, 2026-01-27 <https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>.
Schmid: agent harness 2026, 2026-01-05 <https://www.philschmid.de/agent-harness-2026>; writing good
agents, 2026-02-24 <https://www.philschmid.de/writing-good-agents>; testing skills, 2026-03-04
<https://www.philschmid.de/testing-skills>; agent skills tips, 2026-04-13
<https://www.philschmid.de/agent-skills-tips>. Osmani, good spec, 2026-01-13
<https://addyosmani.com/blog/good-spec/>; Hashimoto, my AI adoption journey, 2026-02-05
<https://mitchellh.com/writing/my-ai-adoption-journey>; LangChain, harness engineering, 2026-02-17
<https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering>; Stripe, Minions part
2, 2026-02-19 <https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2>;
Poehnelt, rewrite your CLI for AI agents, 2026-03-04
<https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/>; Debois, CI/CD for context,
2026-03-05 <https://tessl.io/blog/cicd-for-context-in-agentic-coding-same-pipeline-different-rules>;
Böckeler, harness engineering, 2026-04-02 <https://martinfowler.com/articles/harness-engineering.html>;
Cognition, multi-agents working, 2026-04-22 <https://cognition.com/blog/multi-agents-working>;
Karpathy, Sequoia Ascent 2026, 2026-04-30 <https://karpathy.bearblog.dev/sequoia-ascent-2026/>; Yan,
working with AI, 2026-05-03 <https://eugeneyan.com/writing/working-with-ai/>; Breunig, prompt debt,
2026-06-22 <https://www.dbreunig.com/2026/06/22/the-problem-is-prompt-debt.html>; Weng, harness,
2026-07-04 <https://lilianweng.github.io/posts/2026-07-04-harness/>; Parlance Labs, auto-evals,
2026-07-11 <https://parlance-labs.com/blog/posts/auto-evals/index.html>.

**Read 2026-10-01 for this revision.** Every source re-read for a figure added on 2026-10-01 is
marked "re-read 2026-10-01" where it is cited. Sources newly cited, all read that day: Pecher et
al., underspecification and prompt sensitivity <https://arxiv.org/abs/2602.04297>; Dongre et al.,
drift in multi-turn interactions <https://arxiv.org/abs/2510.07777>; Mason, declarative rules
across languages <https://arxiv.org/abs/2603.25015>; Sclar et al., ICLR 2024
<https://arxiv.org/abs/2310.11324>; He et al. <https://arxiv.org/abs/2411.10541>; Dobariya and
Kumar, prompt tone <https://arxiv.org/abs/2510.04950>; Wharton Prompting Science Report 3, tipping
and threats <https://arxiv.org/abs/2508.00614>; Mind Your Step (by Step)
<https://arxiv.org/abs/2410.21333>; Cheng et al., chain-of-thought exemplars
<https://arxiv.org/abs/2506.14641>; Wang et al., few-shot harm to reasoning models
<https://arxiv.org/abs/2509.23196>; Tang et al., excessive examples <https://arxiv.org/abs/2509.13196>;
Wan et al., NeurIPS 2024 <https://arxiv.org/abs/2406.15708>; ETGPO <https://arxiv.org/abs/2602.00997>;
Geng et al., COLM 2026 <https://arxiv.org/abs/2602.21223>; NoLiMa, ICML 2025
<https://arxiv.org/abs/2502.05167>; Miller, adding error bars to evals <https://arxiv.org/abs/2411.00640>;
Proof-Carrying Numbers <https://arxiv.org/abs/2509.06902>; NIST CAISI, evaluation of DeepSeek models,
2025-09-30
<https://www.nist.gov/news-events/news/2025/09/caisi-evaluation-deepseek-ai-models-finds-shortcomings-and-risks>;
GitHub changelog, hidden Unicode warning, 2025-05-01
<https://github.blog/changelog/2025-05-01-github-now-provides-a-warning-about-hidden-unicode-text>,
and bidirectional text, 2021-10-31
<https://github.blog/changelog/2021-10-31-warning-about-bidirectional-unicode-text/>; GitHub Docs,
setting guidelines for repository contributors
<https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors>;
Git documentation, gitattributes <https://git-scm.com/docs/gitattributes> and diff options
<https://git-scm.com/docs/git-diff>; Factory, agent readiness product page
<https://factory.com/product/agent-readiness>.

**OutcomeBound's records (O).** The results marked (O) in S1, S9, S12, S14, S15, §3, §5, §7, §8,
§9 and §11 come from OutcomeBound's own evaluations, audits, reviews and generated documents,
re-checked against those records on 2026-10-01; the per-rule review in §10 reads
`docs/prompt-standard.md`.
