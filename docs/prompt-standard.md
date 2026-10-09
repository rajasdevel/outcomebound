# The prompt standard

- **Checked:** 2026-09-27, each rule's key records read as fact-checked; the corrections to those
  records' readings made on 2026-10-01 left every rule's confidence, tiers and direction as
  stated; S23 added 2026-10-04 on OutcomeBound's own recorded results.
- **Volatility:** monitor: a rule moves when its evidence does, most often at a model generation.
- **Re-check when:** the research repository's references are refreshed (its
  [CONVENTIONS.md](https://github.com/rajasdevel/outcomebound-research/blob/main/CONVENTIONS.md)
  says when), or a key record a rule cites is corrected.

The rules OutcomeBound's model-facing text follows, S1 to S23, each with the evidence behind it, the
evidence's class, the reader tiers that evidence covers, its confidence and direction, and the
instruction-audit checks that hold it: `outcomebound instructions check` runs seven, S4's five,
S14's `stale-reference` and S7's `load-resolution`, and a rule reading `Checks: none` is held by review or by a test of
OutcomeBound's own text. It is dated evidence, checked 2026-09-27, and revised as "Revising the
standard" says; it names no model, vendor or harness. Classes: M measured, L lab or vendor guidance,
S standards body, P practitioner consensus, A anecdote, F forecast, O OutcomeBound's own recorded
result. An id resolves in the research repository's ledgers,
[`_evidence/*.jsonl`](https://github.com/rajasdevel/outcomebound-research/tree/main/_evidence);
`practice §`, `models` and `harnesses §` name sections and rows of its
[`practices/writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md)
and the files under its
[`models/`](https://github.com/rajasdevel/outcomebound-research/tree/main/models) and
[`harnesses/`](https://github.com/rajasdevel/outcomebound-research/tree/main/harnesses); an O cite
names this project's own recorded result there or in [`docs/evaluations.md`](evaluations.md).

## The rules by layer

Each rule sits under the first layer whose text it governs; the placement table below says what each
layer carries.

### Code: checks, refusals, gates, renderers

**S2** Enforce must-hold rules outside prose (permissions, hooks, sandbox, CI, linter, structured
output) and name the enforcement; render or check in code outputs with more than about five
required parts\
Evidence: `research-3` (M), `research-29` (M), `deterministic-9` (L), `deterministic-10` (L),
`instruction-file-security-authority-22` (L), `measured-f2` (M)\
Tiers: frontier, mid\
Confidence: high; direction: rising\
Checks: none

**S4** Treat instruction files, skills, memory and harness configuration as untrusted: scan before
reading, pin third-party ones, review changes as code, load only when trusted; mark brought-in
material as data\
Evidence: `instruction-file-security-authority-1` (S), `instruction-file-security-authority-12`
(M), `instruction-file-security-authority-15` (M), `instruction-file-security-authority-30` (M)\
Tiers: frontier\
Confidence: high, the brought-in-material clause's effect UNVERIFIED; direction: rising\
Checks: `hidden-characters`, `concealed-content`, `override-phrases`, `harness-config`,
`instruction-change`

**S5** Make done a runnable pass-or-fail check; reports name what was checked and call the rest
unverified\
Evidence: `deterministic-28` (M), `deterministic-8` (L), `forward-15` (M),
`capability-tier-readers-11` (M)\
Tiers: frontier, small\
Confidence: high; direction: rising\
Checks: none

**S11** Treat text as an assumption: remove one group of lines at a time and re-run the same
scenarios per tier at each generation and point release\
Evidence: `forward-1` (M), `forward-5` (M), `measured-g18` (M); against: `research-27` (M)\
Tiers: frontier, mid\
Confidence: high for the method, medium for removal on small readers; direction: rising\
Checks: none

**S13** Add a line, check or tool only after an observed failure, classed as capability, context or
structure, in the most deterministic form that fixes it\
Evidence: `research-7` (M), `latent-space-1` (A), `forward-26` (A)\
Tiers: frontier, small\
Confidence: medium; direction: stable\
Checks: none

**S14** Make every path, command, flag, id, version and rule named agree with its source; check
agreement first; hold it with a test\
Evidence: `repo-readiness-audits-25` (M), `repo-readiness-audits-19` (A), `practice §8 step 1` (O)\
Tiers: frontier\
Confidence: high; direction: rising\
Checks: `stale-reference`

**S16** Size verification to risk, in checks outside the model; no generic double-checking or
thinking depth in prose\
Evidence: `research-22` (M), `research-23` (M), `forward-11` (L), `forward-16` (M)\
Tiers: frontier\
Confidence: medium; direction: self-check prose fading\
Checks: none

### Command output

**S6** Write tool and check output for an agent reader\
Evidence: `deterministic-29` (M), `research-12` (M), `deterministic-2` (L), `other-labs-23` (S)\
Tiers: frontier\
Confidence: high; direction: rising\
Checks: none

For an agent reader: the first line is the verdict and its counts, such as `FAIL 2 of 14 claims`;
each item that did not pass follows on one line with what it is, its verdict, why, and after
`next:` what settles it; passing detail appears only under `--verbose` or `--json`; nothing
prompts, consent being a flag; the exit status is one a script can branch on, 0 only when nothing
failed; `--json` validates against a schema that changes only by added optional fields; and
`--help` names the verbs, flags, what the command reads and writes, and its exits, its usage line
spelling the command as its reader runs it. A command that prints a document, such as a brief,
keeps the document's shape and holds its status line to these.

### Adapter notes and harness settings

**S3** Keep one model's tuning (model names, effort, thinking, dates, narration, formatting,
restated harness rules) in adapter notes and settings, not portable text\
Evidence: `capability-tier-readers-1` (L), `capability-tier-readers-25` (M), `agent-files-8` (M),
`capability-tier-readers-20` (M), `practice §4.2` (L)\
Tiers: frontier, mid, small\
Confidence: high that tiers differ, medium on one text serving them; direction: rising\
Checks: none

### On-demand skills and references

**S10** Keep skills compact, curated and single-purpose; the description is the trigger, key use
case in the first 250 characters, within every listing cap; multi-workflow skills open as routers\
Evidence: `research-8` (M), `research-9` (M), `agent-files-10` (M), `agent-files-17` (L),
`harnesses §5–§6` (L)\
Tiers: frontier\
Confidence: high for compact, medium for the description; direction: rising\
Checks: none

**S18** Prefer typed parameters, enums and commands to tool-use prose; give an example where it
conveys a requirement no statement or schema carries (an output format, a convention, a usage
pattern); no empty expertise claims or try-harder lines, a role that assigns responsibilities being
no persona\
Evidence: `forward-3` (L), `forward-20` (M), `advanced-tool-use` (M), `capability-tier-readers-27`
(M)\
Tiers: frontier, small\
Confidence: medium-low; direction: tool-use examples fading on frontier\
Checks: none

### Always-loaded text

**S1** State outcome, scope and each rule's reach, completion bar (a runnable check or observable
result, plus output shape), bounds and stops, once, up front\
Evidence: `research-18` (M), `research-14` (M), `research-28` (M), `capability-tier-readers-7` (L)\
Tiers: frontier, mid, small\
Confidence: high; direction: rising\
Checks: none

**S7** Know how each harness finds, ranks, caps and compacts each layer; put what must load in the
root `AGENTS.md` and a `SKILL.md`'s top; stay under the tightest cap\
Evidence: `harness-loading-coverage-7` (L), `harness-loading-coverage-8` (L),
`harness-loading-coverage-19` (M), `harness-loading-coverage-21` (L)\
Tiers: frontier\
Confidence: high as facts, which drift; direction: rising\
Checks: `load-resolution`

**S8** Always-loaded text holds only what readers would get wrong without it: unseen conventions,
unguessable commands, gotchas, invariants\
Evidence: `research-4` (M), `research-5` (M), `research-17` (M), `other-labs-29` (M); against:
`research-27` (M)\
Tiers: frontier, mid, small\
Confidence: high on direction, medium on size; direction: rising\
Checks: none

**S9** State each rule once, in one vocabulary, without contradiction across co-loaded text; say
which source wins a collision\
Evidence: `capability-tier-readers-10` (M), `capability-tier-readers-21` (M), `practitioners-4`
(P); against: `research-3` (M)\
Tiers: frontier, mid, small\
Confidence: high; direction: rising\
Checks: none

**S12** Keep always-loaded text a short map: pointers carry a condition and go one level deep;
knowledge most tasks need stays inline as an index\
Evidence: `agent-files-5` (M), `other-labs-29` (M), `forward-29` (M)\
Tiers: frontier\
Confidence: medium; direction: contested\
Checks: none

**S15** Define autonomy by class of action: name what proceeds; stop only before destructive,
irreversible, external or money-spending acts, scope widening, or person-only input; bound every
delegate's brief\
Evidence: `forward-6` (L), `open-weight-f13` (L), `capability-tier-readers-13` (L),
`models Do 4` (L)\
Tiers: frontier\
Confidence: high for one policy, medium for its form; direction: rising\
Checks: none

**S17** Reserve always, never, must and only for exceptionless rules; judgment as conditions; no
weight by capitals, bold or repetition; concrete bars, not vague filters\
Evidence: `forward-10` (L), `capability-tier-readers-8` (L), `other-labs-1` (L); against:
`research-15` (M)\
Tiers: frontier, mid\
Confidence: medium; direction: rising for frontier readers\
Checks: none

**S19** Give a reason only where it changes a decision or covers unnamed cases\
Evidence: `forward-14` (L); against: `other-labs-15` (A)\
Tiers: frontier\
Confidence: low; direction: contested\
Checks: none

**S20** Name what an answer or handoff must contain rather than asking for brevity; no open-ended
thrift wording\
Evidence: `models Do 7` (L), `models Stop 8` (A)\
Tiers: frontier, mid, small\
Confidence: low to medium; direction: rising\
Checks: none

**S21** Leave the path to the reader unless the path is a requirement\
Evidence: `capability-tier-readers-6` (L), `research-28` (M); against: `capability-tier-readers-16`
(M), `capability-tier-readers-22` (M), `capability-tier-readers-26` (M)\
Tiers: frontier, mid, small\
Confidence: contested; direction: unsettled\
Checks: none

### Files that persist across sessions

**S22** Keep a long run's goal, completion check, bounds and progress in files that survive
compaction and new sessions\
Evidence: `measured-g5` (M), `models Do 14` (L)\
Tiers: frontier\
Confidence: medium; direction: rising\
Checks: none

### Every layer

S23 binds the model-facing text of each layer above: the contract, the kernel, the templates,
the fragments and the skills.

**S23** A number or a stop in model-facing text names its evidence: a limit on size, count,
length, duration, attempts or spending appears only where the operator set it, a harness
documents it or a measurement backs it, the source beside it or in the area's design; a stop
holds one item and names the act or check that holds it, never the run\
Evidence: `docs/evaluations.md` E14 (O); `practices/agent-workspace.md` §7 (O); the goal
template's size stop, shipped from a class-O row and removed 2026-10-04 (O)\
Tiers: frontier, mid, small\
Confidence: medium; direction: rising\
Checks: none; held by `tests/test_model_text_limits.py` over the contract, the kernel, the
templates, the fragments and the skills

## The placement table

An obligation goes to the first layer that can carry it.

| Layer | Carries | Does not carry |
| --- | --- | --- |
| Code: checks, refusals, gates, renderers | invariants, schemas, counts, parsing, rendered shapes, many-part outputs, completion gates the agent does not author, freshness and security scans | the model's reasoning or choice of approach (`deterministic-23`) |
| Command output | the computed fact or next step when it matters; a verdict per claim with its fix | passing detail by default; opaque codes (`deterministic-13`) |
| `--help` | a command's procedure: verbs, flags, reads and writes, exit codes; a skill sends its reader here for a step only where the help states that step | what a reader must know before choosing to run it |
| Adapter notes and harness settings | effort, thinking, narration, autonomy and date advice for one model | anything portable |
| On-demand skills and references | a workflow's judgment, gotchas first (`harness-loading-coverage-8`); exact commands where a step is fragile; a trigger-condition description | knowledge most tasks need; narrated rationale; exhaustive edge cases; logic a command can run |
| A delegate's brief | the four inputs and the bounds; concrete steps where the implementer is weaker than the author | any assumption that the delegate shares the author's context |
| Always-loaded text | outcome, done-when, bounds, stops; unseen conventions and gotchas; unguessable commands; pointers with conditions; what must survive compaction (`harness-loading-coverage-7`) | procedure; overviews; style a linter holds; one model's habits; anything text loaded with it states |
| Files that persist across sessions | a long run's goal, completion check, bounds and progress (S22) | rules a project depends on that belong above |
| User-level and memory files | personal preferences | anything a project depends on (`harness-loading-coverage-28`) |

## Severity

An audit orders its findings by the class of rule they bear on, most severe first.

1. Security (S4)
2. Agreement (S14)
3. Loading (S7)
4. No runnable done-check (S5)
5. Must-hold rules enforced only in prose (S2)
6. Contradictions and duplicates (S9)
7. Unneeded content (S8, S11)
8. Wording (S16–S19)

## Contested

S12, S19 and S21 stand below the bar a rule change needs ("Revising the standard"): no check holds
them, and a reviewer weighs them rather than applying them.

## Revising the standard

A revision follows the research: a refresh of the research repository's references, whose
[CONVENTIONS.md](https://github.com/rajasdevel/outcomebound-research/blob/main/CONVENTIONS.md) says
when one is due. Each rule the refreshed records bear on is reviewed against the records as fact-checked, by the
method in §8 of the research repository's
[`practices/writing-for-models.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/practices/writing-for-models.md),
and the **Checked** date at the top of this page moves with the review. S1 to S19 are practices
of that repository; S20 to S23 are OutcomeBound's own additions. A rule changes only on an independent measurement,
guidance from two or more independent groups, or a recorded run of OutcomeBound's own; one lab's
advice for one model becomes a note in the research repository's
[`models/README.md`](https://github.com/rajasdevel/outcomebound-research/blob/main/models/README.md)
instead. A rule resting on a
falsified forecast, or whose direction reversed, is reopened. The revision moves the checked date
and each changed rule's evidence, tiers, confidence and direction, names each check it adds or
retires, and says in the changelog what changed for a reader. Changing a rule, deciding on the lines
that the research repository's model files hold for the next revision, and requesting an eval run for a revision are
decisions for the project's maintainers.
