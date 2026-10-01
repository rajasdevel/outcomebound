---
last_checked: 2026-10-01
volatility: MONITOR (lab guidance on verifiers and code review changes with model releases; the measured studies and the recorded runs do not)
sources:
  - https://arxiv.org/abs/2502.04313
  - https://arxiv.org/abs/2404.13076
  - https://arxiv.org/abs/2006.14779
  - https://arxiv.org/abs/2602.14611
---

# Independent review of agent work

When a second reader of an agent's work or of the spec it runs from adds signal, which reader to
use, how many rounds a large spec takes, and how to carry a review's findings until each is fixed
and shown fixed.

Re-check when a lab changes its guidance on fresh-context verifiers or code review, a study compares
same-family with cross-family review of code at equal effort, or a new model family joins the
reviewers in use. Evidence ledger records are as verified on 2026-09-25 and 2026-09-26.

This reference answers when an independent reader of work an agent did, or of a plan it will run
from, finds something no check found; whether that reader should come from the author's model
family or another; what a review's verdict does and does not establish; how many rounds a large,
decision-complete spec takes; what happens to findings deferred as minor; and how to verify that
the fixes a review accepted actually landed. It is for anyone who decides whether work needs a
second reader, chooses the reviewer and its brief, runs review rounds on a spec, or keeps the
findings a review leaves. How large a change a reviewer can read well is in
[work-breakdown.md](work-breakdown.md) F8; judges that score evaluation runs are in
[llm-as-judge.md](llm-as-judge.md), [evaluations.md](evaluations.md) and
[writing-for-models.md](writing-for-models.md) §9.

**Evidence classes.** (M) measured; (L) a lab's or vendor's guidance or its report about its own
product; (P) practitioner consensus; (A) one person's view or one uncontrolled report; (O) a result
recorded in one repository's own runs and reviews. Each key finding carries a strength: **strong**
(several independent measured results, or measurement plus convergent guidance), **moderate**
(guidance or one repository's records plus some independent measurement), **weak** (one source or
anecdote). `UNVERIFIED` marks what the evidence does not establish.

**Citations.** Bracketed ids resolve by `id` in [`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl),
or in [`_evidence/2026-09-26.jsonl`](../_evidence/2026-09-26.jsonl) for `sizing-` ids. Papers and
pages without a record are cited by arXiv number or name and listed under Sources with the day
they were read. "One repository's runs" means the development of one tool repository in September
2026, in which Claude-family agents (Claude Opus 5, Claude Fable 5, Claude Sonnet 5) implemented
work packages and tickets, a fresh-context Claude reviewer read each, and OpenAI models through
Codex (gpt-6-astra, gpt-5.6-sol) reviewed adversarially and read-only; its review reports, run
ledgers and verification files were read again on 2026-10-01.

## Key findings

**RV1. A fresh-context second reader finds what the author, the suite and self-review missed.**
Maintainers would not merge about half of the test-passing agent pull requests they read
[sizing-horizon-19]; Anthropic's long-run guidance prefers separate fresh-context verifiers, which
"tend to outperform self-critique" [sizing-trend-32]. In one repository's runs every reviewed
ticket needed a repair, and a check engine with about 2,200 passing tests drew 2 Critical and 11
Important findings from an outside review. Strong: independent measurement, convergent guidance and
own records. (M, L, O) — §1.

**RV2. When the author and its reviewers share a model family, add a reviewer from another
family.** Judges favour models similar to themselves and the mistakes of capable models grow
more alike (arXiv 2502.04313). In one repository's runs, work every Claude reviewer had approved
drew eight blocking defect groups from a gpt-6-astra review; six reproduced, one in part, none was
refuted. Moderate: no run held brief and effort equal across families, so the family's share of
that is `UNVERIFIED`. (M, O) — §2.

**RV3. A finding is a claim and a GO is one reader's reading.** Reproduce each finding before
fixing it; one reviewer's claim was false and reviewers withdrew three of their own. After a tenth
review round returned GO on a plan, a read-only scan by another model found 9 conflicts and 24
ambiguities in it. Moderate. (O, M) — §3.

**RV4. A decision-complete spec for a smaller implementer takes many rounds, and each correction
pass opens new gaps.** A seven-file spec drew NO-GO in nine consecutive adversarial rounds and GO
in the tenth while it grew from about 4,900 to about 6,200 lines; 22 of the 26 packages built from
it then needed at least one fix round. Plan the rounds, or cut the spec's ambition, before relying
on one review. Moderate: two review loops in one repository. (O) — §4.

**RV5. Findings deferred as minor go stale and hide defects: re-verify each against the tree
before deciding it.** Of 71 deferred items triaged one by one, 2 let a shipped check pass over a
defect, 15 had already been fixed and 1 needed the person; the ledgers' own counts, line citations
and "already fixed" notes were wrong in places. Moderate: one repository's ledgers. (O) — §5.

**RV6. Verify that accepted fixes landed with a pass aimed at that alone.** Fix rounds introduce
new defects: a fresh probe of one fix round closed 14 findings, one only partly, and found new
ones; in a check engine every re-review for seven rounds found new Important defects in the code
the round before had written. Moderate. (O, A) — §6.

**RV7. Point each review at one lens and say what to check.** Three scoped rounds (engine against
contract, tests against claims, documents against source) returned 15 findings, all reproduced;
rule-guided code review recovered 98% of required custom findings against a 58.3% baseline
[openai-25]. Moderate. (O, M, vendor) — §7.

**RV8. Size the review to the change: both its yield and its cost grow with scope.** One vendor's
reviewer found issues on 84% of pull requests over 1,000 changed lines and 31% under 50
[sizing-review-23]; in one repository's runs a fresh-context review of one ticket's diff took
67k–152k tokens and of one larger work package 149k–252k. Moderate. (M, vendor; O) — §7.

## 1. When a second reader adds signal

A reader adds signal where no runnable check covers the risk: a test that stays green with the
behaviour broken ([testing.md](testing.md) K1), a sentence that disagrees with the code or a
sibling document, a decision that exists only in code, a change of meaning in rewritten text, or a
plan whose packages leave a writer unowned. Where a command can decide the question, the command is
the better reader.

**Outside evidence.**

- Maintainers reviewing 296 agent-written SWE-bench Verified pull requests would not merge roughly
  half of those that passed the tests, about 24 points below the grader after normalizing to a 68%
  baseline for the original human patches [sizing-horizon-19] (M). On 18 real issues, Claude 3.7
  Sonnet passed the maintainers' tests 38% of the time, but none of 15 reviewed pull requests was
  mergeable as it stood [sizing-horizon-18] (M).
- Anthropic's long-run guidance makes verification explicit: "Separate, fresh-context verifier
  subagents tend to outperform self-critique" [sizing-trend-32, forward-12]; the longer an agent
  works unattended, "the more an independent check matters before you count the work as done"
  [sizing-lab-19] (L). OpenAI asks developers to review long-running Codex work before changes or
  deployment, with Codex review as an additional reviewer, not a replacement [sizing-trend-43] (L).
  Cognition finds that extra agents work best contributing intelligence, such as a clean-context
  reviewer, while writes stay single-threaded [sizing-review-34] (L).
- Anthropic reports that before agent review 16% of its pull requests got substantive review
  comments, and 54% after [sizing-review-24] (L, a vendor about its own product).
- Where a check can be run, give the check: Claude Code's guidance names a fresh-context reviewer
  as one way among several to gate stopping, beside a test loop, a session goal and a stop hook
  [anthropic-20, deterministic-8] (L); "ask it to write a script that verifies", not to verify
  [latent-space-20] (A).

**What independent reviews found in one repository's runs** (O). Every finding below was checked
against the source, and most were reproduced as a failing test, before it was counted.

| What was reviewed | Reviewer | What it found |
| --- | --- | --- |
| A ticket layer's spec | a second outside pass | 9 findings, all accepted |
| That spec, its plan, 18 work packages and two follow-on drafts | one combined pass | 14 findings, all accepted; it also confirmed every package block parsed and every requirement was covered |
| The built ticket layer | an outside reviewer, fresh context, read-only, no test run | 15 findings and 2 suspicions; all 15 reproduced as failing tests before they were fixed |
| An uncommitted installer implementation | several fresh-context reviews and one cross-family adversarial review | 29 reproduced defects and a compatibility gap that would have blocked a release; most consequential decisions existed only in code |
| A check engine with about 2,200 passing tests, after a whole-branch review and its fixes | gpt-6-astra, high effort, read-only | 2 Critical and 11 Important, among them a policy check that a replacement plan running `/usr/bin/true` passed, and one baseline entry that accepted any number of identical new findings |
| The same engine after further fixes, 2,348 passing tests | the same | 3 Critical, 8 Important and 1 Minor, among them an optional new check that silently weakened an accepted gate; all 12 confirmed, 10 by a failing test and 2 by inspection, none disproved |
| An instruction audit's per-surface tables, 14 surfaces | a fresh-context reader of each table | 7 of the 29 disagreements inside the audited text, on 5 of the 14 surfaces, which the first reader had recorded as agreeing |
| Rewrites of a contract, a kernel draft, skills and templates to a writing standard | 8 fresh-context reviews | 6 of the 8 found blocking changes of meaning, 10 distinct; the 2 reviews of the most-read skill found none |

Adopting the same check engine on its own repository found six further defects no test had caught,
and adopting it on another repository found more (O). The per-ticket record is in
[work-breakdown.md](work-breakdown.md) §3: nine of nine reviewed tickets accepted "with fixes", and
17 of 18 fresh-context reviews of larger packages returned "fix".

**Where a reader adds little.** On pull requests under 50 changed lines, Anthropic's agent reviewer
found something on 31%, about 0.5 issues each, against 84% and 7.5 issues over 1,000 lines
[sizing-review-23] (M, vendor). A one-sentence change that an existing test proves is a floor case
for a check, not for a reader ([work-breakdown.md](work-breakdown.md) P3).

## 2. Same family against another family (STABLE)

**One repository's runs** (O, one pair of families):

- **After same-family approval.** Every package of one milestone of an installer rewrite had been
  approved by a fresh Claude Opus reviewer after its fix rounds. A read-only review by gpt-6-astra
  at high effort then reported eight blocking defect groups. An independent Claude verifier
  reproduced six, one in part, found one to be a decision already on record, and refuted none.
- **At a later milestone.** Three scoped gpt-6-astra reviews at medium effort (engine against
  contract, tests against claims, documents against source) returned 15 findings: 2 blocking, 10
  should-fix and 3 nits. All 15 reproduced before any was fixed.
- **A second engine.** A check engine built by Claude-family implementers and passed by
  Claude-family reviewers drew 2 Critical and 11 Important findings from gpt-6-astra at high effort,
  and 3 Critical, 8 Important and 1 Minor from a second pass after further fixes (§1).
- **Misreads.** On re-review, same-family reviewers withdrew three of their own findings as
  misreads.
- **Where two families agree.** Two reviews of one contract rewrite, by models of different
  families, agreed on its blocking change of meaning and differed on whether input only the person
  can give stops the run or is batched while other work continues.

**Why a shared family shares blind spots** (M):

- Across judges and models, "LLM-as-a-judge scores favor models similar to the judge", and "model
  mistakes are becoming more similar with increasing capabilities, pointing to risks from correlated
  failures" (Goel et al., Great Models Think Alike and this Undermines AI Oversight, arXiv
  2502.04313, 2025).
- GPT-4 and Llama 2 distinguish their own outputs from others' with non-trivial accuracy, and
  self-recognition correlates linearly with the strength of self-preference (Panickssery, Bowman and
  Feng, arXiv 2404.13076, 2024).
- Practitioners advise watching a judge for self-preference toward its own family [evals-12] (P).

**What this does not show.** The cross-family reviews were adversarial, read-only, run at high or
maximum effort and briefed with named lenses; the same-family reviews were task reviews of one
package each. No run held the brief and the effort equal and changed only the family, so how much
of the difference the family explains is `UNVERIFIED`. The pair is Claude authors and OpenAI
reviewers; the reverse direction was not run.

## 3. Reading what a review returns (STABLE)

- **Reproduce each finding before acting on it.** Every one of the 15 outside findings on the
  ticket layer, the 15 scoped cross-family findings and the 12 second-pass findings on the check
  engine was reproduced before a fix (§1, §2). Checking against the source caught one false claim
  (that `gh` lacks dependency flags; it has them), and same-family reviewers withdrew three findings
  as their own misreads on re-review (O).
- **A GO establishes that one reader found no blocker.** The tenth review round of a plan returned
  GO and said itself that the verdict did "not establish implemented correctness, harness loading,
  model benefit", or readiness for wider use. A read-only scan of the same plan by a Claude model
  found 9 conflicts and 24 ambiguities; the load-bearing ones were confirmed: an acceptance test the
  plan named did not exist, and three of the spec's files belonged to no package (O).
- **Two readers given the same prompt overlap only in part.** Two fresh-context reviewers of an
  instruction-audit method, with the same prompt and read-only access, raised 25 distinct points in
  a first round, 8 of them by both, and 15 in a second, 6 by both; two second-round points reversed
  first-round dispositions (O). In one rewrite only the edits both of two reviews proposed were
  applied, and each review's lone proposals were left out (O).
- **A persuasive summary is not evidence.** In a study of people working with an AI's
  recommendations, explanations "increased the chance that humans will accept the AI's
  recommendation, regardless of its correctness" (Bansal et al., CHI 2021, arXiv 2006.14779) (M).
  A review's confident prose is weighed like any other claim.
- **A reviewer's severity label is its own.** Items filed as minor included defects that let a
  shipped check pass (§5).

## 4. Review rounds on a large or decision-complete spec (STABLE)

**A spec written so a smaller model decides nothing** (O). A seven-file specification for an installer rewrite was written so that a weaker model could implement its plan
without inventing a decision. A Codex reviewer, gpt-6-astra at maximum effort in the early rounds
and high in the later ones, reviewed it adversarially ten times, and after each round a model
applied the corrections.

- Rounds one to nine returned NO-GO. Each correction pass closed the findings named and exposed or
  introduced new blocking ones: contradictions between files, writers no package owned, sequencing
  gaps, and acceptance commands that could not pass as written. Round ten returned GO.
- The set grew from about 4,900 lines after round two to about 6,200 by round ten.
- Each round sampled rows that described existing code against the source: 5 of 21 were wrong in
  round three, 3 of 17 in round four, 4 of 15 in round five and 1 of 15 in round seven.
- After the GO, the scan in §3 found 9 conflicts and 24 ambiguities in the plan.
- Built from that plan, one Claude Opus 5 implementer at a time worked 26 packages from briefs of
  225–1,327 words that pointed into it, and a fresh Opus reviewer read each result: 22 went back for
  at least one fix round, 4 passed the first review or needed only edits the orchestrator made, and
  one needed five rounds, each closing one more way its grader could be fooled
  ([evaluations.md](evaluations.md), lessons on graders); the cross-family review of §2 read the
  result.

**A review of one repository's whole tree before a release** (O). Ten adversarial loops
by gpt-5.6-sol at high effort, each given the fixes since the last loop and the findings already
accepted: NOT-READY with new blocking findings in loops one to nine, READY in loop ten.

**What follows.** A plan reviewed to GO did not make first-pass implementation right, and a spec
that tries to settle every decision in prose for a weaker reader keeps growing and keeps drawing
blockers. Before starting a loop, set its budget of rounds and what happens when the budget runs
out; sample the spec's claims about existing code against the source each round; and consider the
alternative the sizing evidence favours, charting only as far as knowledge is stable and letting the
implementer's plan carry the rest ([work-breakdown.md](work-breakdown.md) P7). Two loops in one
repository are the whole evidence; no source compares a spec reviewed to convergence with a shorter
spec and checkpoints inside the work.

## 5. Deferred findings (STABLE)

In one repository's runs, findings that reviews marked "minor (deferred)" were kept as prose: two
progress ledgers held 59 such lines with no id and no status (O).

- **Triage against the current source.** Split into 71 items for a check engine and a ticket layer
  and decided one by one against the source, by symbol: 2 were not minor, each letting a shipped
  check pass over a defect (a destructive-SQL scanner split a statement at a `;` inside a quoted
  identifier, so `ALTER TABLE "t;u" DROP COLUMN x;` read clean; a list parameter rendered by joining
  with commas let one recorded acceptance stand for a different change); 1 was a question of intent
  for the person; 15 had already been fixed by later work; 25 became fixes; and 28 were kept or
  dropped with a reason. Of the ticket layer's own seven, 2 were already fixed, 4 kept with a reason
  that changed no verdict and 1 went to the person.
- **The ledgers misled.** Their own counts did not match a mechanical count; cited line numbers had
  moved, or never resolved even at the commit that wrote them; two bullets from different review
  rounds were one defect, and two that read alike were two mechanisms; two items that said no test
  caught a change were caught by a test the ledger did not name. A second ledger (13 packages, 66
  deferred items, separate from the 71 above) had, in 4 packages, a triage note that an item was
  already fixed, or that a name no longer appeared, which was wrong when checked.
- **Re-verify before drafting.** Five drafters who re-checked 44 findings against the tree before
  turning them into tickets dropped 3: one intended behaviour, one already fixed, one already
  ticketed.

A deferred finding therefore names its subject by path and symbol, says which verdict it could
change, and is re-verified against the tree before it becomes work or is closed. One that could let
a check pass over a broken subject, or let a report state something untrue, is not a minor. Turning
every later finding into its own ticket is the other failure: [work-breakdown.md](work-breakdown.md)
§3 records a batch of 35 such tickets with a median diff of 45 lines.

## 6. Verifying that accepted fixes landed (STABLE)

- **A fix round needs its own reading.** After the 15 outside findings on the ticket layer were
  fixed, a reader with fresh context re-ran the review's counter-examples as probes rather than
  trusting the new tests: 14 findings and one suspicion closed, one closed only partly, and new
  defects appeared, among them a page flag of `null` read as "no further page" (O).
- **Fix code is new code.** In the check engine the fix loop ran seven rounds, past its planned cap
  of five, because each re-review found a new Important defect in the code the previous round had
  just written (O). One evaluation grader took five fix rounds, each re-check finding another way
  its effect count could fail open (O; [evaluations.md](evaluations.md) E16).
- **A record of coverage is not a reading of meaning.** Rewrites that carried a sentence-by-sentence
  record of every earlier sentence still changed meaning where the record said "carried": a
  permission became a duty, a gate narrowed to one row of its table, a parenthesis created a new
  stop, a done-when became one no command could meet (O). Review a rewrite against its
  before text ([writing-for-models.md](writing-for-models.md) §8).
- **Fixes land in one place and not another.** In another project's review of a document set, a
  short second pass that checked only whether each accepted fix from an adversarial cross-family
  review had landed found fixes applied on one page and missing or contradicted on another,
  including figures a verification note had corrected that stayed stale elsewhere (A, one other
  project's review records).
- **A correction is a claim too.** In the same project a first pass corrected figures from a stale
  copy of the data; checked against the authoritative source, one of its corrections was wrong and
  the original had been right (A). Record which source each figure came from, and check a
  correction there before it replaces the original.
- **Trace every name across layers.** Checking documents that describe one design by tracing each
  named object through concept, data, schema, owner and example in one table found naming drift
  that page-by-page reading had missed (A, one other project's review records).

For each accepted finding, list every place its claim appears, check each one, and re-run the
reviewer's own reproduction against the fixed tree.

## 7. Setting up a review

- **Fresh context, read-only, its own copy.** Every review above read with no memory of the work,
  in a worktree or detached copy, and changed nothing. A reviewer that must run checks needs a
  writable disposable copy: reviews run in Codex's read-only sandbox could not run the project's test
  suite or create temporary fixtures, so their acceptance re-runs read `UNVERIFIED` and their
  findings rested on reading the source and in-memory probes (O; the harness details are in
  [harnesses.md](../harnesses/cross-harness.md#3-loading-harness-by-harness)).
- **One lens a round, and the question asked.** The three scoped rounds of §2 split the work by
  lens and every finding reproduced. OpenAI's guidance for Codex code-review rules: start with "a
  consequential, non-obvious invariant", scope rules to the code they govern, and remove guidance
  that keeps producing noise; rule-guided review recovered 98% of required custom findings against
  58.3% without [openai-25] (M, vendor; L). In human review, stating the type of feedback needed went
  with 64–72% higher merge odds across 80,000 pull requests (arXiv 2602.14611, correlational) (M).
- **Give the reviewer the before text and the ground truth.** A rewrite is read against what it
  replaced; a review of figures is given the source the figures come from (§6).
- **Effort is not a dial for quality.** On one vendor's code-review benchmark for Claude Opus 5.5,
  turning effort up "did not consistently produce a better review" [claude-f23] (M, vendor, one
  model).
- **Diff size.** For one small model (Claude Haiku 4.5), review F1 fell from 0.657 on diffs under 10
  lines to 0.043 over 150 lines [sizing-review-22] (M, 150 samples); a reviewable landing unit is a
  few hundred lines at most ([work-breakdown.md](work-breakdown.md) F8).

**What reviews and the fix rounds they send cost** (O, from recorded token counts unless a row says
otherwise):

| Review | Model, effort | Tokens |
| --- | --- | --- |
| Review of one ticket's diff, fresh context | a larger Claude model | 67k–152k ([work-breakdown.md](work-breakdown.md) §3) |
| Review of one larger work package | a larger Claude model | 149k–252k |
| A fix round handed to a fresh delegate, which must re-read the work first | a larger Claude model | about 134k (A: one run whose record was not kept) |

## How to apply

1. Give the agent a check it can run wherever one can decide the question; add a second reader
   where none can: meaning, agreement between documents and code, tests that pass with the behaviour
   broken, plans with gaps (RV1).
2. Make the reader independent: fresh context, read-only, its own copy, and a writable disposable
   copy if it must run checks (§7).
3. Where the author and its reviewers share one model family, add a reviewer from another family at
   the points that matter most: a milestone, a release, a spec before it is built (RV2).
4. Give each review one lens and the question it must answer, with the before text or the source
   of truth beside it (RV7).
5. Reproduce every finding before fixing it; treat a GO as one reader finding no blocker, and a
   severity label as the reviewer's opinion (RV3).
6. Budget the rounds of a spec review before starting, sample the spec's claims about existing code
   each round, and prefer a shorter spec with checkpoints inside the work over prose that settles
   every decision for a weaker reader (RV4).
7. Keep a deferred finding with its path, symbol and the verdict it could change, and re-verify it
   against the tree before deciding or drafting it (RV5).
8. After a fix round, run a pass that checks only whether each accepted fix landed, everywhere its
   claim appears, re-running the reviewer's reproductions (RV6).
9. Scale the review to the change: a short focused review for a small change, a broad adversarial
   one before a release (RV8).

## Limits and open questions

- The own-run evidence is one repository, September 2026, Claude-family authors and same-family
  reviewers against OpenAI reviewers through Codex. The other project's records (§6) are one set of
  reviews of documents, carried as rules without their counts.
- No source compares same-family with cross-family review of code at equal brief and effort, or a
  second same-family reviewer with a first cross-family one.
- Yields count reproduced findings, not escaped defects: what every review missed is known only
  where a later review found it.
- The outside measurements of review effectiveness predate agents or concern human maintainers
  ([work-breakdown.md](work-breakdown.md) F8); the measured agent-reviewer results are a vendor's
  own (Anthropic, CodeRabbit, OpenAI) or small (150 samples).
- Open: how many rounds a spec should get before its ambition is cut; whether a fix-landing pass
  catches as much as a full re-review at lower cost; whether agreement between two reviews of
  different families predicts a finding that holds.

## Sources

Evidence records: [sizing-horizon-18], [sizing-horizon-19], [sizing-trend-32], [forward-12],
[sizing-lab-19], [sizing-trend-43], [sizing-review-34], [sizing-review-24], [sizing-review-23],
[sizing-review-22], [anthropic-20], [deterministic-8], [latent-space-20], [evals-12], [openai-25],
[claude-f23].

Papers read 2026-10-01: Goel et al., Great Models Think Alike and this Undermines AI Oversight,
arXiv 2502.04313 (2025-02-06, revised 2025-06-12); Panickssery, Bowman and Feng, LLM Evaluators
Recognize and Favor Their Own Generations, arXiv 2404.13076 (2024-04-15); Bansal et al., Does the
Whole Exceed its Parts? The Effect of AI Explanations on Complementary Team Performance, CHI 2021,
arXiv 2006.14779. Cited from [work-breakdown.md](work-breakdown.md): arXiv 2602.14611.

Own records (September 2026), read 2026-10-01: one repository's adversarial review reports and their
verification files, the run ledgers of two work-package runs and a ticket layer, its triage records,
a pre-flight scan of a plan and the session records of two review loops. One other project's review
records of a document set (2026-09), read 2026-10-01; carried as rules without their counts and not
re-checked.
