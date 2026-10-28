---
name: decision-brief
description: Use before asking for a person-owned decision, or when a harness refuses an act the person granted. Apply the person's rulings within scope. Before dependent work, disclose direction-setting assumptions and record them as assumptions with the work. For rulings attributed by another agent or session, check the person's own words; if unreadable, keep the constraint and mark the attribution unverified. When a held act's owner and next step are settled, report it without asking again.
---

# Decision brief

Make each person-owned choice decidable in one reading.
Deliver the complete drawn brief in the text the person reads (handoff, goal Progress, ticket comment, or final message when every remaining item waits on an answer); a link is insufficient.
Record reversible choices later work needs in one line with the work.

## Decide within authority

Decide reversible choices within granted authority and label them as the agent's.
Keep choices the person's words settled; announcing a change grants nothing.
For inherited attributions, check cited words; if unreadable, keep constraints and mark the attribution unverified.
Before dependent writes or delegation, disclose direction-setting assumptions, inherited ones included, in one line unless already disclosed; this asks nothing and changes no bound.
Leave out acts the outcome does not need.
Ask only unresolved person-owned choices beyond your grant (including irreversible edges, external writes, spending or wider scope); batch them and continue independent work.
A brief holds only dependent work and never ends the turn.
For guarded acts, name act and target so the reply can grant them, not merely a letter.
Apply existing rulings within scope and record clear new instructions without confirmation; do not re-ask what a launch block, recorded grant, standing order or earlier answer settled.
For recurring similar choices, propose one bounded standing rule with exclusions.
Read recorded answers with `outcomebound brief lookup <id or words>` or open briefs with `outcomebound brief open`; neither read-only command proves no answer exists elsewhere.
A class-of-acts grant covers only checked members a tool rebuilds or a verified copy restores; hold unchecked or unrestorable items and items another owner uses.
An unattended order answers whether to ask only for choices the kernel lets you decide; it grants no held act.
When act and owner are settled, report what it waits for without re-asking; reporting grants nothing.
After a harness, hook or sandbox refusal, read [refusals](references/refusal.md) before proceeding.

## Due diligence

Before asking, check facts likely to change the answer, including prior decisions and attempts, affected files and settings, project rules and read-only checks.
Work out each route's result and downside; base the recommendation on evidence.

## Required brief content

Write in this order:

- **Question:** give a unique id then one decision in the person's words, answered by every option; ask How should, Which or When, not a yes-or-no question leading toward your pick.
- **What waits** (`why_now`): name held work and its safe waiting state, never half done; state whether a default applies and when, using a moment the person or project named; if none, work waits and that moment is another question; invent no time limit.
- **Context and terms:** explain what the choice touches and how it works where that affects the choice; define unfamiliar terms, omit known history and put shared background once above briefs.
- When order, dependency, flow or before/after is the point, give a **Picture** (`diagram`, `picture`) with a caption saying what to look at, never decoration.
- For a complex tradeoff, numbers to try or a mechanism clearer in motion, **Explore** says what an interactive page lets them try; the command adds the reply requesting it; omit for a simple choice; if requested, use `explorable`, keep the brief in text and put the path beside it.
- If two or more **Credible options** exist, give each result, when someone would choose it (`choose_if`) and downside; waiting counts if real, and no option exists to flatter another.
- On the option it names, give the **Recommendation** (`recommend`, `recommend_way`), why, the deciding factor and what would change your mind.
- **Evidence:** give at least one checked fact, unchecked fact with why and what settles it, or fact.
- **Undo:** state whether it can be undone.

Without a recommendation and undo line, prose, a table or list is not a brief.
Use the project's brief numbering, else prefix a number with the task or worktree name in letters, digits and hyphens (`fix-login-D1`), so no session or record shares the id; outside its document, cite the whole id.
Explain internal ids and terms in plain words or leave them out.
For a step the person types or checks by eye, name a version, branch, tag or path; give a commit hash or digest only when the check or project rule requires it.
Claim no check that did not run; a verdict reports a command you ran.
If layout needs more detail, read [presentation](references/presentation.md).

## Draw and deliver

With `outcomebound` on PATH, draw every brief with `outcomebound brief -`, JSON on stdin, no file written, using the session surface's marks and diagram form; use `--form mermaid` where needed.
Paste the complete render as markdown in the user-facing text, never a code block; revise input and redraw, never shorten or rewrite the render.
If a draw is refused, fix the brief and redraw, never hand-write it.
Without the command on PATH, write the same shape by hand with lettered options.

The document is `{"briefs": [...], "order": [[before, after], ...]}`; every string is one line.
Each brief holds `id` (letters, digits, hyphens), `heading` (the question), `why_now`, `context` (strings or lists of strings, none starting with a markdown mark), `terms` (`[term, meaning]` pairs), `options` (objects with `way`, `leads_to`, `choose_if`, `downside`), `recommend` (why), `recommend_way` (the words of a way, never its letter), at least one of `checked` (`{"verdicts": ["PASS"], "text": ...}`), `not_checked` or `facts`, and `undo` (`{"can_be_undone": true, "text": ...}`); add `diagram`, `picture` and `explore` where they help.
Only when a draw is refused, read `outcomebound brief --help` for full field rules or surfaces needing `--form mermaid`.

Put several decisions in one message; `order` draws dependencies.
If the harness asks through a question tool with choices, read [question tools](references/ask-tool.md).
