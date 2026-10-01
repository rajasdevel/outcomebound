---
last_checked: 2026-10-01
volatility: MONITOR (the evidence on what helps and the supply-chain risks change at a model generation) / VOLATILE (§1 listing caps, §6 public sets)
sources:
  - https://agentskills.io
  - https://code.claude.com/docs/en/skills
  - https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
  - https://claude.dev/blog/lessons-from-building-claude-code-how-we-use-skills/
  - https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra.md
  - https://developers.openai.com/blog/eval-skills.md
  - https://arxiv.org/abs/2602.12670
  - https://arxiv.org/html/2607.01456v1
  - https://arxiv.org/html/2608.08453v1
  - https://arxiv.org/html/2601.10343
  - https://arxiv.org/html/2602.06547v1
  - https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals
  - https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/
  - https://github.com/mattpocock/skills
  - https://github.com/obra/superpowers
  - https://github.com/anthropics/skills
---

# Agent skills: what works, what they are for, and the public sets compared

Which agent skills help, how to write and vet one, and what three public skill sets offer.

Re-check when a harness changes how it lists or truncates skills, or one of the public sets ships a
release; in any case by 2026-12-25, a quarter after the sweeps. Evidence ledger records are as
verified on 2026-09-25; the figures added since and the public sets were re-read on 2026-10-01.

This reference answers what the evidence says about agent skills (the `SKILL.md` folders a coding
harness lists by name and description and loads on demand): which kinds of skill help and which
harm, how to write the description and the body, what makes a skill a supply-chain risk, which pains
of people running coding agents a skill can address, what three public skill sets offer for those
pains (credited by name), and how a skill earns its place. It is for anyone deciding which skills to
write, sharpen, borrow or cut. Where harnesses find and list skills is in
[harnesses.md](../harnesses/cross-harness.md#6-skills-discovery-and-listing) §6; the general practices for model-facing text are in
[writing-for-models.md](writing-for-models.md), where skills are practice S10.

## Key findings

1. **Compact, curated skills help; comprehensive documentation does not; self-generated skills do
   harm.** Curated skills raised the average pass rate from 33.9% to 50.5% (+16.6 points), compact
   (+19.0) and standard-length (+21.5) skills against +0.7 for comprehensive documentation; focused skills of at most three modules beat
   exhaustive bundles, and smaller models with skills can match larger ones without them.
   Self-generated skills landed below the no-skill baseline on Opus 4.7, GPT-5.5 and Gemini 3.1 Pro.
   Measured [research-8, research-9, agent-files-7].
2. **The description is the trigger, and the model sees only a truncated listing until it invokes
   the skill.** Write it as the condition for use, with the key use case first: Claude Code cuts it
   at 1,536 characters in the model's listing, Codex shortens it to fit 2% of context or 8,000
   characters, ZCode injects 250 characters and drops a skill over 1,024. Lab-guidance
   [agent-files-17, chk-claude-skills, openai-14, glm-f23].
3. **For knowledge most tasks need, an always-loaded index beat an on-demand skill.** An 8 KB docs
   index in `AGENTS.md` scored 100%; the skill was never invoked in 56% of cases and peaked at 79% even
   when told to use it. Measured, vendor [other-labs-29].
4. **Constraints written inside a skill are the least-followed kind of instruction** for every model
   tested, closed ones included (Opus 4.5 58%, Sonnet 4.5 52%). Must-hold rules belong in hooks or
   code. Measured [open-weight-f7, qwen-f14].
5. **Skills are a supply chain.** In 98,380 skills, 84.2% of vulnerabilities sat in `SKILL.md` and
   73.2% of malicious skills carried undocumented features; of 3,984 public skills, 36.82% had a
   security flaw, and 2.9% of those on ClawHub fetched and ran remote content at run time; daily
   submissions rose from under 50 to over 500. Measured
   [instruction-file-security-authority-15, instruction-file-security-authority-14].
6. **Skills written for older models over-prescribe for newer ones.** Itineraries and recipes that
   once helped now hinder capable models; a multi-workflow skill should open as a short router.
   Lab-guidance [openai-15, capability-tier-readers-2, anthropic-6].
7. **Verification skills pay most.** Anthropic found bundled scripts that drive the real product
   and assert on its state had "the most measurable impact" on output quality. Lab-guidance
   [agent-files-18].
8. **A skill earns its place only against a baseline.** Run it with and without the skill in the
   same batch, on cases where it should and should not fire; until then its benefit is
   `UNVERIFIED`. Lab-guidance and practitioner-consensus [evals-24, other-labs-21, openai-26,
   evals-8].
9. **The three public sets read here (Matt Pocock's skills, superpowers, Anthropic's public skills)
   hold ideas worth adapting but none is reusable verbatim** in text meant for several harnesses:
   each names a harness, a vendor's tools, its author, or its reader as "your human partner".
   Anecdote (a reading of the texts; no skill was run).

## 1. What a skill is, across harnesses (VOLATILE)

- **Format.** A folder with a `SKILL.md` whose frontmatter carries at least a name and a
  description, plus optional references and scripts; only the name and description are preloaded,
  and the body loads when the skill is invoked (the Agent Skills standard, which began at Anthropic)
  [claude-harness, other-labs-19]. Eleven checked harnesses read this format; their directories
  differ ([harnesses.md](../harnesses/cross-harness.md#6-skills-discovery-and-listing) §6). The specification defines six frontmatter fields:
  `name` and `description` required; `license`, `compatibility` and `metadata` optional; and
  `allowed-tools`, optional and experimental. About 100 tokens of metadata per skill load at
  startup, the instructions are recommended under 5,000 tokens and the `SKILL.md` under 500 lines,
  and bundled resources load only when required; a script's output enters the context, while
  Anthropic's skill-creator says its scripts can run without being loaded (L, agentskills.io and
  its source read 2026-10-01). The site listed 46 supporting products on that date, up from 44 at
  the start of August 2026.
- **Tool definitions load the same way in Claude Code.** Tool search is on by default: MCP tools
  are deferred and discovered on demand; an opt-in mode loads them up front while their definitions
  stay under 10% of the context window (L, Claude Code MCP docs read 2026-10-01).
- **Harness extensions.** Claude Code adds invocation control, `context: fork`, `effort` frontmatter
  and `paths` [claude-harness]. Qwen Code gates skills by `paths:` and lets frontmatter declare hooks
  as hard gates [qwen-f13, qwen-f14]. Grok Build reads `when-to-use`, `paths`, `argument-hint`,
  `user-invocable` and `disable-model-invocation`; its `allowed-tools` neither grants nor restricts
  tools, and `model`, `effort`, `license` and `compatibility` are accepted and ignored
  [grok-harness]. Gemini CLI loads a body only after `activate_skill` and the user's consent
  [gemini-harness]. Antigravity requires a description [gemini-harness].
- **Listing budgets.** Claude Code: 1,536 characters per description in the model's listing, 250 in
  the `/skills` menu; after compaction each invoked skill keeps its first 5,000 tokens, 25,000 in
  all, oldest dropped first [chk-claude-skills, harness-loading-coverage-8]. Codex: the listing is
  capped at 2% of context or 8,000 characters, descriptions shortened when there are many
  [openai-14]. ZCode: name plus the first 250 characters each turn, a description over 1,024 drops
  the skill, and a shared budget degrades to names only when too many skills are enabled [glm-f23,
  glm-harness].

## 2. What the evidence says

- **Curated and compact** (above, key finding 1). In SkillsBench v4 (2026-06-14; 87 tasks with
  deterministic verifiers, 18 model–harness configurations) curated skills raised the pass rate
  from 33.9% to 50.5%, with per-configuration gains of +4.1 to +25.7; by length, detailed skills
  gained +14.5, between standard (+21.5) and comprehensive (+0.7, a bin of five tasks); one skill
  gained +18.0, two or three +19.0 and four or more +10.1; 13 of the 87 tasks got worse with
  skills, and software engineering (+11.6) and mathematics (+9.7) gained least. v1 (2026-02-13;
  seven configurations) said focused skills of 2–3 modules outperform comprehensive documentation,
  put software engineering lowest at +4.5, and found 16 of 84 tasks worse. Self-generated skills,
  written with Anthropic's skill-creator, scored 8.1–11.5 points below no skill where curated ones
  added 18.2–24.8 on the same three configurations [research-8, research-9, agent-files-7; v1 and
  v4 re-read 2026-10-01] (M).
- **Organisation changes behaviour before outcomes.** In one study of 82 SkillsBench tasks,
  rewriting skills so that only their organisation changed (progressive disclosure, scope and
  thresholds held fixed) raised the distinct resources touched per trajectory from 1.18 to 3.85 and
  skill-uptake events from 1.33 to 3.92, but gave a modest overall gain, +4.1% (17 more passing of
  410 matched trials, inside a paired interval of ±6.0), helping when supporting resources guide
  implementation, checking or repair, and weaker when success hinges on exact output conventions,
  numerical thresholds or long artifact pipelines [research-10; re-read 2026-10-01] (M).
- **Descriptions.** "The description field is not a summary, it's a description of when to trigger
  this skill" [agent-files-17] (L). Skill descriptions should be "as short as possible while making
  it clear when the model should use them" [openai-f21] (L). Skills that passed six routing-metadata
  checks scored 88.5% hit@1 against 82.6% in a lexical retrieval test; the gap is observational, no
  description was repaired and re-measured, and lexical retrieval does not mirror a model's skill
  selection [agent-files-10] (M). In the same study's 138,133 skill files from 20,556 repositories,
  91.8% had at least one detected defect and 89.3% broke the specification; missing trigger
  guidance (52.3%) and the skill's name repeated as its heading (44.3%) led [agent-files-10;
  re-read 2026-10-01] (M, prevalence only). Two fixes, rewriting one skill's description to match
  the user's intent rather than the API's terms and replacing passive deprecation warnings with
  explicit instructions, took it from 66.7% to 100% over about 20 test cases; the description change
  alone fixed 5 of 7 failures [other-labs-15; re-read 2026-10-01] (A).
- **An inline index or a skill.** For knowledge needed on most tasks (such as version-specific
  framework APIs), a compact index in the always-loaded file beat invoking a skill; keep skills for
  vertical, user-triggered workflows [other-labs-29] (M, vendor). A default skill scored the same
  as no docs (53%); telling the agent to use it raised the result to 79% and the trigger rate to
  95% or more, and the wording of that instruction mattered: "You MUST invoke the skill" read the
  docs first, anchored on their patterns and missed project context, where "explore the project
  first, then invoke the skill" did better, with no separate pass rate given for each wording
  [other-labs-29 detail; post re-read 2026-10-01] (M, vendor). Agents never followed a link from
  one document to another as a tool call in one observational study [agent-files-5] (M). Whether the
  gap closes as models improve is forecast P3 in [models.md](../models/cross-family.md#8-forecasts).
- **Closing a knowledge gap.** A skill pointing agents to the docs as the source of truth lifted
  Gemini 3 models from a low baseline (6.8% for 3.0 Pro and Flash, 28% for 3.1 Pro) on SDK changes;
  measure against a no-skill baseline, expect the gain mainly on strong reasoning models, and plan how
  the skill gets updated, since stale installed skills do "more harm than good" [other-labs-9] (M,
  lab-own).
- **Skill-file constraints are weakly followed** (key finding 4): Gemini-3-Pro 43%, Doubao 31% and
  open models 12–43%, against higher rates for system reminders and memory [open-weight-f7] (M,
  January 2026 models; benchmark co-authored by MiniMax).
- **Bodies persist.** Once loaded, a skill's body stays in context for every later turn, so every
  line is a recurring cost: "State what to do rather than narrating how or why" [anthropic-12] (L).

## 3. Writing a skill

- **Trigger-first description**, the key use case within the first 250 characters (the tightest
  injection limit), under 1,024 characters overall, not repeating the skill's name as its heading
  [glm-f23, agent-files-17, chk-claude-skills].
- **Only what the agent would get wrong without it.** "Would the agent get this wrong without this
  instruction? If the answer is no, cut it"; exhaustive coverage hurts because agents follow
  instructions that do not apply [other-labs-19] (P). A skill is not a central store of every known
  practice [forward-4] (L). "Too much guidance becomes non-guidance. When everything is 'important,'
  nothing is" [openai-20] (A).
- **Gotchas first.** The highest-value content is often a list of environment-specific facts that
  defy reasonable assumptions, placed where the agent reads it before meeting the situation, and
  extended with every correction [other-labs-20] (P). Compaction keeps the start of a skill, so what
  matters goes near the top [harness-loading-coverage-8].
- **Match freedom to fragility.** Exact scripts with no variation for fragile, sequence-critical
  operations; heuristics where many approaches are valid; bundled scripts rather than model-written
  code for deterministic work [anthropic-18] (L). Say what to achieve and which constraints hold,
  not the path; when exact steps matter, put them in a script [other-labs-14] (P).
- **Route, do not narrate.** For several workflows, make the root a minimal router to supporting
  docs and scripts [capability-tier-readers-2] (L); do not write itineraries [openai-15] (L).
- **Advisory size.** Keep a `SKILL.md` under 500 lines (Anthropic's authoring guidance)
  [anthropic-18]; a size limit is an advisory, not a measured threshold.
- **Portable text.** A skill meant for several harnesses "cannot assume they all provide identical
  capabilities" [latent-space-29] (A); keep one model's tuning out of it (writing-for-models S3).
- **Re-test at each model release.** Revisit skills with each new model; Matt Pocock advises fewer
  and smaller skills [other-labs-30] (A); skills written for earlier models are "often too
  prescriptive" for Fable 5 [anthropic-6, claude-f9] (L).
- **Readers who never load the instruction file.** Where a harness or helper loads a skill without
  the always-loaded file, and no pointer can make it load, the skill carries the minimal
  restatement its reader needs; elsewhere it states each rule once (reasoning).
- **Reaching the reader.** A skill no install carries, or whose references are not copied with it,
  reaches no one; text moved into a skill counts as carried only where the reader's harness loads it
  (writing-for-models S7). A reference file `SKILL.md` never names reaches only a reader who lists
  the skill's folder: in one audited skill, a field list and the rule that an export is optional
  sat in such a file (O). Name each reference from `SKILL.md`, with the condition for
  reading it.

**Common defects when a skill is read against the text it sits beside** (observed in one
repository's review of its own skills; anecdote): restating the always-loaded contract; setting a second
ask policy that conflicts with the contract's; statements the tool it describes does not bear out;
and a name that promises a pain its body does not address. A superpowers finding points the same
way: a description that summarises the workflow gets followed instead of the body.

**Smell catalogues.** A published taxonomy of 26 skill smells, drawn from 29 practice sources and
detected by 5 static checks and 21 model checks (weighted F1 0.78), finds smells in all but one of
238 `SKILL.md` files analysed; its most prevalent, "Rationalization Loophole", is in 94%. It was not
tested against outcomes, and some smells ("Never Asks Human", "No Progress Tracking") reward the
added prescription current lab guidance removes, so treat its hits as questions, not defects
[agent-files-9; re-read 2026-10-01] (M).

## 4. Skills as a supply chain

- **Where the risk sits.** 84.2% of vulnerabilities in 98,380 skills sat in `SKILL.md`; 73.2% of
  malicious skills carried undocumented features. Read instruction text for coercive language
  ("NON-NEGOTIABLE", "SEVERE VIOLATION"), secrecy directives ("do NOT mention in conversation") and
  autonomy overrides ("DO NOT ASK THE USER"), and compare what a skill documents with what it does
  [instruction-file-security-authority-15] (M).
- **Fetched content.** Flag any skill that fetches instructions or code at run time (`curl … |
  source`, `curl | bash`): "The published skill appears benign during review. But attackers can
  modify behavior at any time by updating the fetched content" [instruction-file-security-authority-14]
  (M). In the same scan of 3,984 skills on ClawHub and skills.sh, 36.82% had at least one security
  flaw, 13.4% a critical one, and 21% of known-malicious samples fetched remote content
  [instruction-file-security-authority-14; re-read 2026-10-01] (M, vendor). Add a CI Unicode lint
  that rejects skill files, tool-server manifests and AI configuration
  files containing Tag-block code points or unusual densities of zero-width characters
  [instruction-file-security-authority-10] (P); prefer an allowlist of permitted non-ASCII over a
  list of bad characters [instruction-file-security-authority-8] (A).
- **Before deploying a skill:** read all of it; check for directives to ignore safety rules, hide
  actions, exfiltrate data or change behaviour on specific inputs; check network calls and
  credentials; weigh file-read plus network tools together [instruction-file-security-authority-18]
  (L). Pin third-party skills and review changes to them like code (writing-for-models S4 and §7).

## 5. Pains a skill can address

Gathered from the research in these references and from running coding agents under an operating
contract, most severe first. Anecdote; the ranking and the two severity bands are
judgments, and the last column points to the reference that holds the evidence for each pain. Ids
SP01–SP15.

| Id | Pain | Severity | Where the evidence is |
| --- | --- | --- | --- |
| SP01 | Unattended runs stall where the process, not the work, needs the person, and lose their thread | high | [agent-workspace.md](agent-workspace.md) §7 |
| SP02 | Process outweighs the change | high | [testing.md](testing.md) §2; [work-breakdown.md](work-breakdown.md) §3 |
| SP03 | Work cut to the wrong size: too many tickets, or too-large asks | high | [work-breakdown.md](work-breakdown.md) §4–§5 |
| SP04 | Tests that cannot fail for the reason they name | high | [testing.md](testing.md) K1–K4, K9 |
| SP05 | "Done" that is not evidence | high | [testing.md](testing.md) K10 |
| SP06 | Specs, tickets and reports too long for the person to read | high | [work-breakdown.md](work-breakdown.md) §5; [writing-for-models.md](writing-for-models.md) §11 |
| SP07 | A project that starts red: failing tests and old findings | high | [testing.md](testing.md) §1; [quality-floor.md](quality-floor.md) Q7 |
| SP08 | Decisions and work lost across sessions | high | [agent-workspace.md](agent-workspace.md) §3–§4 |
| SP09 | An unclear outcome: guessing, or asking too much too late | high | [writing-for-models.md](writing-for-models.md) S1 |
| SP10 | Too many questions | medium | [evaluations.md](evaluations.md) E3 |
| SP11 | A repository shared with other developers | medium | [agent-workspace.md](agent-workspace.md) §2 |
| SP12 | Authority the harness cannot read | medium | [agent-workspace.md](agent-workspace.md) §5, §7 |
| SP13 | Instruction sprawl | medium | [harnesses.md](../harnesses/cross-harness.md#131-one-practitioners-account-t1t7) §13.1 T1; [writing-for-models.md](writing-for-models.md) §7.1 |
| SP14 | Incomplete changes | medium | [work-breakdown.md](work-breakdown.md) F2 |
| SP15 | Untrusted input | medium | [writing-for-models.md](writing-for-models.md) §7.3; [agent-workspace.md](agent-workspace.md) §4 |

**Gaps no public skill filled** (as read): a baseline of pre-existing failing tests, taken before a
change and reported apart (SP07); an unattended run's continuity, with milestones, a progress file
and an independent progress check in harness-neutral text (SP01); and making documents shorter by
measurement rather than by advice (SP06).

## 6. The public skill sets compared (VOLATILE)

Every `SKILL.md` of Matt Pocock's skills (main at c55ee460, plugin 1.2.3) and superpowers (6.4.1),
and the relevant ones of Anthropic's public skills, were read in full on 2026-09-29. The facts below
were re-read on 2026-10-01 against superpowers 6.4.1 and 6.4.2, Matt Pocock's skills at the v1.2.3
tag (2026-08-06) and on main (d81f3a18), and Anthropic's skills at 8a1541c4 (2026-09-29, no tags);
where the sets changed in between, the text says which version it means. Judgments come from
reading the text; no skill was run.

| Set | Licence | Stance | Worth adapting |
| --- | --- | --- | --- |
| Matt Pocock's skills | MIT | 37 skills on main at 2026-10-01 (35 at the v1.2.3 tag, whose plugin ships 25), human-driven (the core ones gate on "confirm with the user"), no evals, coupled to their own setup skill | diagnosing-bugs' first phase (a red-capable, deterministic, fast loop before any fix); tdd's anti-patterns (tautological and implementation-coupled tests); to-tickets' expand-contract for wide refactors; domain-modeling's three-part test for when a decision earns a record; writing-for-agents' pruning test ("does it change behaviour versus the default?"); code-review's split of spec from standards; pr's one-way or two-way door; grilling's whole frontier in one round; loop-me's "push right: ask once, late, with everything prepared" |
| superpowers | MIT | Process-maximising: a skill that might apply must be invoked; iron laws; approval gates. The opposite stance on sizing | writing-good-tests (name the break, no change detectors, behaviour not text, a mutation check); systematic-debugging's core (instrument each boundary, one hypothesis at a time, stop after three failed fixes); receiving-code-review's "if any item is unclear, implement nothing yet"; writing-skills' tested finding that a description summarising the workflow gets followed instead of the body |
| Anthropic's public skills | no licence at the repository root; an Apache-2.0 `LICENSE.txt` in 15 skills (skill-creator, discernment-nudge, webapp-testing, mcp-builder, frontend-design, claude-api and academy-guide among them); none in doc-coauthoring; docx, pdf, pptx and xlsx "All rights reserved", which the README calls source-available | — | doc-coauthoring's reader test: a fresh agent reads only the document and answers the questions a reader would ask, the one idea found for SP06; with no stated licence, none of its text is copied |

**Reuse.** None is reusable verbatim in text meant for several harnesses: each names a harness, a
vendor's tools, its author or "your human partner". MIT text adapted into another tree keeps its
copyright and permission notice, and Apache-2.0 text keeps its licence and notices. A skill can
carry another author's text: Pocock's `pr` skill reproduces part of another author's skill "almost
word for word" by its own `CREDITS.md`, so that part is that author's. superpowers' README says it
does not generally accept new skills, so its ideas travel by adaptation. An interviewing skill such
as Pocock's `grilling` is what a person installs to be questioned, which is a reason for another
skill to treat such a request as granting the questions.

**Sizes and specifics** (re-read 2026-10-01; A, a reading). In words of `SKILL.md` alone:
superpowers' `subagent-driven-development` 4,871, `writing-skills` 3,814, `executing-plans` 3,267,
`brainstorming` 2,613 and `test-driven-development` 1,475 (its `writing-good-tests.md` 1,310
more); 13 of its 15 skills exceed the 500 words its own `writing-skills` sets for a skill that is not
loaded often (under 200 for one that is). Anthropic's `skill-creator` 5,205 and `doc-coauthoring`
2,466. Matt Pocock's `implement` 70, `tdd` 559, `to-tickets` 894 and `wayfinder` 2,000 on main (567,
909 and 2,019 at v1.2.3). superpowers' `brainstorming` puts a hard gate before any implementation
and lists "too simple to need approval" as an anti-pattern; `test-driven-development`'s iron law
deletes code written before its test, exceptions only with "your human partner"; `executing-plans`
keeps a ledger and a stop list, and `writing-plans` asks the person to choose an execution method;
`using-superpowers` makes invoking any skill that might apply mandatory. Pocock's `to-tickets` cuts
vertical tracer bullets "sized to fit in a single fresh context window" and quizzes the user on
granularity; `implement` hands the result to an agent review skill; `tdd` confirms the seams under
test with the user before writing any test. Neither set has a skill that tells a model when to skip
process.

**One set moved toward proportion.** superpowers 6.4.2 (released 2026-09-25) rewrote
`writing-plans`: "A plan is the set of decisions the implementer cannot make alone. A plan longer
than the code it describes has written the code instead", with a self-review step comparing the
plan's length to the spec's; 6.4.1 had asked for code blocks in every code step, steps of 2–5
minutes, and an engineer with "zero context" (A, both versions read 2026-10-01).

**One text for ten harnesses.** superpowers reaches about ten harnesses by shipping a manifest or
plugin for each (Claude Code, Codex, Cursor, Devin, Hermes, Kimi, Muse, OpenCode, Pi, Gemini) with
per-harness tool notes, and injects its entry skill when a session starts through each harness's
own mechanism: a session-start hook where one exists, an include or a message transform elsewhere
(A, 6.4.2 read 2026-10-01).

**Ideas credited, with where they come from.**
- Name the production change that would fail the test; assert on real behaviour, not on what a
  double returns; no change detectors on constants, exact wording or private structure; a mutation
  check once a test file is done: superpowers 6.4.1,
  `skills/test-driven-development/writing-good-tests.md` (MIT). A break-then-restore step is that
  mutation check done by hand; the method is mutation testing, DeMillo, Lipton and Sayward, "Hints on
  Test Data Selection: Help for the Practicing Programmer", IEEE Computer, 1978.
- A red that is an error, a typo or a different assertion is not the red: superpowers 6.4.1,
  `skills/test-driven-development/SKILL.md`, "Verify RED".
- Tautological and implementation-coupled tests, and expected values from a source the code did not
  produce: Matt Pocock's skills 1.2.3, `skills/engineering/tdd/SKILL.md` and `tests.md` (MIT). Older
  statements of the same: James Carr, "TDD Anti-Patterns" (2006, "the liar", "the mockery"); Google
  Testing Blog, "Test Behavior, Not Implementation" (2013) and "Change-Detector Tests Considered
  Harmful" (2015).
- Deterministic, behavioural, structure-insensitive tests: Kent Beck, "Test Desiderata" (2019). The
  root causes of flaky tests and why a retry hides them: Luo, Hariri, Eloussi and Marinov, "An
  Empirical Analysis of Flaky Tests", FSE 2014; Google Testing Blog, "Flaky Tests at Google and How
  We Mitigate Them" (2016).
- A bug's test reproduces the reported symptom through a check that can go red before any fix: Matt
  Pocock's skills 1.2.3, `skills/engineering/diagnosing-bugs/SKILL.md`, phase 1.
- A first-run pass is diagnosed, not forced red; the evidence against a reproduce-first rule is
  FixedBench (arXiv 2605.07769) [research-28].
- Separating what the person said from what was assumed, marking each requirement stated or
  inferred: superpowers 6.4.1, `skills/brainstorming/SKILL.md`. Asking once, late, with everything
  prepared: Matt Pocock's `loop-me`. Finding facts before asking: Pocock's `grilling`.
- A run stops only for an irreversible or destructive operation, a security-sensitive action, a
  side effect outside its worktree, or a plan so broken that every path is a guess; every other
  choice is recorded as a ruling, what was decided, why and what it costs if wrong: superpowers
  6.4.1, `skills/executing-plans/SKILL.md` (MIT).
- The most expensive failure observed was a controller that lost its place and re-dispatched
  completed tasks, hence a ledger; "turn count beats token price"; batch small work of one shape;
  hand artifacts to a delegate as files, since what is pasted into a dispatch stays in the
  controller's context: superpowers 6.4.1, `skills/subagent-driven-development/SKILL.md`.
- A reviewer lists what it declined to judge and treats a spec's silence as no permission:
  superpowers 6.4.1, `skills/requesting-code-review/code-reviewer.md`.
- Match the form of a rule to the failure: a prohibition for rule-breaking, a positive recipe for
  output of the wrong shape: superpowers 6.4.1, `skills/writing-skills/SKILL.md`.
- Before text leaves a private project, scrub eight categories (email addresses, people, account
  identifiers, secrets, hosts, home paths, repositories, proprietary terms), then have an
  independent auditor look for what the scrub missed, until it finds nothing: superpowers 6.4.1,
  `skills/diagnosing-superpowers/references/redaction-policy.md`.
- A claim needs its evidence ("tests pass" needs the test command's output):
  `skills/verification-before-completion/SKILL.md`. Say which path a request gets, so the person can
  override it: `skills/brainstorming/SKILL.md` (both superpowers 6.4.1).
- Reproduce a reported problem from the reporter's steps before questioning it, search for an
  existing implementation by domain concept rather than the request's words, and keep a record of
  what is out of scope so it is not argued again: Pocock, `triage`.
- A question is ready for a ticket when it can be stated precisely, whether or not it can yet be
  answered; produce decisions, not deliverables: Pocock, `wayfinder`.
- A handoff references what other artifacts already hold, by path or URL, and does not copy it:
  Pocock, `handoff`. A document that restates the environment is a cache: Pocock,
  `writing-for-agents`. A mechanical violation gets a deterministic check: Pocock, `retro`.
- Resolving a merge conflict preserves both intents and invents no behaviour; the same skill's
  "never `--abort`" removes the exit when intent cannot be traced, and its "stage everything" sweeps
  unrelated changes into the merge: Pocock, `resolving-merge-conflicts` (at v1.2.3; removed from
  main on 2026-09-24).
- A hook that matches `git push` as a substring of the command, unanchored, misses `git -C dir push`
  and can block pushes the person authorised: Pocock, `git-guardrails-claude-code`. Parallel
  implementers communicate through context pointers, with a separate merger: Pocock,
  `implement-spec`. The pains his README names: the agent did not do what was wanted, the agent is
  too verbose, the code does not work, a ball of mud.
- ALWAYS or NEVER in capitals is a yellow flag; a helper every test run writes again belongs bundled
  with the skill; the same text asks for descriptions "a little bit pushy": Anthropic,
  `skill-creator` (Apache-2.0). Run a bundled script with `--help` first and do not read its source:
  Anthropic, `webapp-testing` (Apache-2.0). Code the person will run needs no verification nudge,
  since running it is the verification: Anthropic, `discernment-nudge` (Apache-2.0).

## 7. How a skill earns its place

1. **It addresses a real pain** (§5) that the always-loaded text does not already cover, and does
   not restate that text.
2. **It changes behaviour against the default** ("does it change behaviour versus the default?",
   Pocock's pruning test), shown by a paired run: with and without the skill (or against its
   previous version) in the same batch, flagging assertions that always pass or always fail in both
   configurations and evals that vary run to run [evals-24, other-labs-21] (L, P).
3. **It fires when it should and not when it should not:** 10–20 prompts in a set that grows, with
   `should_trigger=false` negative controls, deterministic checks on the traces, and a rubric where
   rules fall short [openai-26, evals-8] (L).
4. **It holds across the models that will load it,** re-tested at each model release
   [other-labs-30, anthropic-6].
5. **It reaches its reader:** installed where the reader's harness lists skills, with its references,
   and under every listing cap.

Harnesses have begun to ship eval tooling for skills: Claude Code added eval plugins that test
whether a skill makes things better, at a token cost and imperfectly ([harnesses.md](../harnesses/cross-harness.md#131-one-practitioners-account-t1t7)
§13.1 T1).

## How to apply

- Before writing a skill, name the pain and check that no always-loaded line or existing skill
  already covers it.
- Write the description as the trigger, key use case first, inside 250 characters.
- Keep the body to gotchas, judgment and exact scripts for fragile steps; route multi-workflow
  skills; put must-hold rules in hooks or code.
- Scan third-party skills before installing, pin them, and review their changes like code.
- Measure a skill with and without it, on cases where it should and should not fire, before
  trusting it.

## Limits and open questions

- The measured skill results come from a few benchmarks (SkillsBench, SkillJuror, one retrieval
  study, OctoBench) and one vendor's comparison; none tests one skill across current flagships of
  several families.
- The public-set comparison is a reading of text on two days (2026-09-29 and 2026-10-01); no skill
  was run, and the sets change between releases.
- The pains are reported, not measured; their order is a judgment.
- Whether an index keeps beating an on-demand skill as models improve is open (forecast P3).

## Sources

Read 2026-09-25 unless dated. Evidence ids resolve in
[`_evidence/2026-09-25.jsonl`](../_evidence/2026-09-25.jsonl).
- SkillsBench, 2026-02-13 (v4 2026-06-14) <https://arxiv.org/abs/2602.12670>; SkillJuror, 2026-06-10
  <https://arxiv.org/abs/2606.11543>; Anatomy to Smells, 2026-07-01 <https://arxiv.org/html/2607.01456v1>;
  138K `SKILL.md` files, 2026-08-09 <https://arxiv.org/html/2608.08453v1>; OctoBench, 2026-01-15
  <https://arxiv.org/html/2601.10343>; malicious skills (Liu et al.), 2026-02-06
  <https://arxiv.org/html/2602.06547v1>.
- Anthropic: how we use skills, 2026-06-03
  <https://claude.dev/blog/lessons-from-building-claude-code-how-we-use-skills/>; skill authoring
  best practices <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>;
  skills for enterprise <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise>;
  skill-creator, 2026-03-06
  <https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md>; the new
  rules of context engineering, 2026-07-24
  <https://claude.dev/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models/>;
  Claude Code skills <https://code.claude.com/docs/en/skills> [chk-claude-skills].
- OpenAI: rethinking skills and prompts for GPT-6 Astra, 2026-09-11
  <https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra.md>; eval skills,
  2026-01-22 <https://developers.openai.com/blog/eval-skills.md>; harness engineering, 2026-02-11
  <https://openai.com/index/harness-engineering/>.
- Google: closing the knowledge gap with agent skills, 2026-03-25
  <https://developers.googleblog.com/closing-the-knowledge-gap-with-agent-skills/>; Schmid, agent
  skills tips, 2026-04-13 <https://www.philschmid.de/agent-skills-tips>; testing skills, 2026-03-04
  <https://www.philschmid.de/testing-skills>.
- Agent Skills: best practices (2026-04-19) <https://agentskills.io/skill-creation/best-practices>;
  evaluating skills (2026-03-13) <https://agentskills.io/skill-creation/evaluating-skills>; using
  scripts (2026-02-27) <https://agentskills.io/skill-creation/using-scripts>.
- Vercel, `AGENTS.md` outperforms skills in our agent evals, 2026-01-27
  <https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals>; Snyk, ToxicSkills on
  ClawHub, 2026-02-05 <https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/>; CSA,
  Unicode instruction injection in skills, 2026-03-10
  <https://labs.cloudsecurityalliance.org/research/csa-research-note-unicode-instruction-injection-ai-skills-20/>;
  Latent Space, AIEWF 2026 trends, 2026-07-14 <https://www.latent.space/p/aiewf26trends>; ZCode skills
  <https://zcode.z.ai/en/docs/skill>.
- Public skill sets, read 2026-09-29 and re-read 2026-10-01: Matt Pocock's skills (main at
  c55ee460 and d81f3a18, tag v1.2.3, MIT) <https://github.com/mattpocock/skills>; superpowers 6.4.1
  and 6.4.2 (MIT) <https://github.com/obra/superpowers>; Anthropic's public skills at 8a1541c4
  <https://github.com/anthropics/skills>.
- Read 2026-10-01: Agent Skills specification and overview <https://agentskills.io> (source
  `agentskills/agentskills` at 69ef37e9); Claude Code MCP docs, tool search
  <https://code.claude.com/docs/en/mcp>; Snyk ToxicSkills, the SkillsBench (v1 and v4),
  SkillJuror, Anatomy to Smells and 138K `SKILL.md` papers, and Vercel's comparison, re-read for the
  figures added that day.
- Testing literature credited in §6: DeMillo, Lipton and Sayward, IEEE Computer, 1978; James Carr,
  "TDD Anti-Patterns", 2006; Google Testing Blog, 2013, 2015 and 2016; Kent Beck, "Test Desiderata",
  2019; Luo, Hariri, Eloussi and Marinov, FSE 2014.
