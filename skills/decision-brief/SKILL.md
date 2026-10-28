---
name: decision-brief
description: Use when you are about to ask the person for a decision that is theirs to make, or when a harness refuses an act the person granted. Apply a ruling the person already made within its scope; say a direction-setting assumption before work builds on it and record it as an assumption where the work is recorded; check a ruling another agent or session attributes to the person against their own words, and where those words cannot be read keep the constraint and mark the attribution unverified; report a held act whose owner and next step are settled without asking again.
---

# Decision brief

Done means the person can decide each person-owned choice in one reading: the complete drawn
brief is in the text they read (handoff, goal Progress, ticket comment or final message when
every remaining item waits on an answer). A link to a brief file is not the brief. Record each
reversible choice later work depends on in one line where the work lives.

## Decide within authority

Decide reversible choices inside granted authority yourself. Preserve choices the person's words
settled; announcing a change grants nothing. Check inherited attributions against cited words;
if unreadable, keep the constraints and mark the attribution unverified. Label agent choices as
such. Before dependent writes or delegation, disclose a direction-setting assumption in one line
unless already disclosed, including inherited assumptions. The line asks nothing and changes no
bound. Leave out an act the outcome does not need.
Ask only unresolved person-owned choices: acts beyond your grant, including irreversible edges,
external writes, spending or wider scope. Batch them and continue independent work. A brief
holds only dependent work and never ends the turn. For guarded acts name the act and target so
the person's reply can grant them, not only a letter.

Apply existing rulings within scope and record clear new instructions without confirmation.
Do not ask again what a launch block, recorded grant, standing order or earlier answer settled.
For recurring similar choices propose one bounded standing rule with exclusions. Read the
recorded answer with `outcomebound brief lookup <id or words>` or open briefs with
`outcomebound brief open`; neither read-only command proves no answer exists elsewhere.
A class-of-acts grant covers only checked members that a tool rebuilds or a verified copy
restores. Hold unchecked or unrestorable items and items another owner uses. An unattended order
answers whether to ask only for choices the kernel lets you decide; it grants no held act.
If act and owner are settled, report what it waits for without asking again;
the report grants nothing. After a harness, hook or sandbox refusal, read
[refusals](references/refusal.md) before proceeding.

## Due diligence before asking

Check facts likely to change the answer: prior decisions and attempts, affected files and
settings, project rules and read-only checks. Work out each route's result and downside; let
the evidence choose the recommendation.

## Required brief content

Write in this order:

- **Question:** after a unique id, one decision in the person's words. Each option answers it;
  use How should, Which or When, not a yes-or-no question leading toward your pick.
- **What waits** (`why_now`): work held and its safe waiting state, never half done. State
  whether a default applies and when, using a moment the person or project named. If none,
  work waits; that moment is another question. Invent no time limit.
- **Context and terms:** what the decision touches and how it works where that affects the
  choice. Define unfamiliar terms. Omit known history; put shared background once above briefs.
- **Picture** (`diagram`, `picture`): if order, dependency, flow or before/after is the point,
  give a picture with a caption saying what to look at, never decoration.
- **Explore:** for a complex tradeoff, numbers to try or a mechanism clearer in motion, say
  what an interactive page lets them try; the command adds the reply requesting it. Omit for
  a simple choice. If requested, use `explorable`; keep the brief in text and put the path beside it.
- **Credible options**, if two or more: each result, when someone would choose it (`choose_if`)
  and downside. Waiting counts if real; no option exists to flatter another.
- **Recommendation** (`recommend`, `recommend_way`): on the option it names, why, deciding
  factor and what would change your mind.
- **Evidence:** at least one checked fact, unchecked fact with why and what settles it, or fact.
- **Undo:** whether it can be undone.

Prose, a table or list without a recommendation and undo line is not a brief. Use the project's
brief numbering, else prefix a number with the task or worktree name in letters, digits and
hyphens (`fix-login-D1`), so no session or record shares the id. Cite its whole id outside the
brief's document. If layout or labels need more detail, read
[presentation](references/presentation.md).

## Draw and deliver

With `outcomebound` on PATH, draw every brief with `outcomebound brief -`: JSON on stdin, no file
written, marks and diagram form for the session's surface. Use `--form mermaid` on surfaces
that need it. Paste the complete rendered brief as markdown in the user-facing text, never a
code block; revise the input and draw again, never shorten or rewrite the render. Fix a refused
brief and draw again, never hand-write it. Without the command on PATH, write the same shape
by hand with lettered options.

The document is `{"briefs": [...], "order": [[before, after], ...]}`; every string is one line.
Each brief holds `id` (letters, digits, hyphens), `heading` (the question), `why_now`, `context`
(strings or lists of strings, none starting with a markdown mark), `terms` (`[term, meaning]`
pairs), `options` (objects with `way`, `leads_to`, `choose_if`, `downside`), `recommend` (why)
and `recommend_way` (the words of a way, never its letter), at least one of `checked`
(`{"verdicts": ["PASS"], "text": ...}`), `not_checked` or `facts`, and `undo`
(`{"can_be_undone": true, "text": ...}`); `diagram`, `picture` and `explore` where they help.
Read `outcomebound brief --help` for full field rules or surfaces needing `--form mermaid` only
when a draw is refused.

Put several decisions in one message; `order` draws dependencies. If the harness asks through
a question tool with choices, read [question tools](references/ask-tool.md).
