---
name: decision-brief
description: Use when you are about to put a question or a held act to the person, or to build on a direction-setting choice they have not settled. Also when a harness refuses an act the person granted.
---

# Decision brief

Put each decision that is the user's so they can make it quickly and make it well. You are done
when the user can make each one in one reading: it is a drawn brief where they will read it (the
handoff, the goal's Progress section, a comment on the ticket it holds, or your final message,
when every remaining item waits on an answer), and each reversible choice you made yourself that later work depends on is
noted in one line where the work is recorded. A link from that text to a file that holds the brief never stands in for
it: the brief itself is in the text.

## Decide what is yours

Decide every reversible choice inside your granted authority yourself. Before the writes or the
delegation that build on an assumption that sets the direction of later work, such as the approach
or which part owns a capability, say it to the person in one line, not first in a report, unless
you can see it was said to them already; this includes one inherited from another agent or
session. The line asks nothing and changes no bound. A choice the person's own words settled stays
as they settled it however easy it is to undo, and a line that announces a change to it does not
grant the change. Check a record that attributes a choice to the person against their cited words;
where those cannot be read, keep its constraints and state the attribution as unverified. A choice
made within granted authority stays labelled as an agent's choice. An act the outcome does not
need is left out, not asked about. Ask the user only what is
theirs — an act your authority does not grant, such as an irreversible edge, an external write,
spending, or widening scope — batched into one message, and continue the work that does not wait
on the answer. A brief never ends your turn: a run starts without answers, and a brief holds only
the work that waits on it, so every other item goes on. Some harnesses honor authority only from
the user's own words: for an act a permission check guards, such as a deletion or a write outside
the project, the brief names the act so the user's reply can state it, not only a letter.

Apply an existing ruling within its stated scope, and record a clear new instruction without
asking the person to confirm it. Where another case needs a choice the person already made for a
similar one, propose one bounded standing rule, with its exclusions, instead of another one-case
question. A question the person already settled is not asked again: their launch block, a grant a
project file records (a tickets declaration), their standing order and their earlier answer stand.
`outcomebound brief lookup <id or words>` prints the answer recorded for a brief, a `Decided:` line
under `.agents/work` or `.agents/handoffs`, or `UNANSWERED`; `outcomebound brief open` lists the
briefs with no such line. Both only read, and neither shows that the person has not answered
elsewhere. An order that names a class of acts, such as clearing what is not needed, grants each item your check shows
is in that class and that a tool rebuilds or a copy you verified restores; hold an item you did not
check, one nothing restores, and one another owner uses. An order to run unattended answers "may I ask" only for
questions within what the kernel allows you to decide; it grants no act that a bound or an edge
holds. Where the act and its owner are already settled, report the held act and what it waits
for: a brief is for an unresolved choice, and the report grants no act. Where a harness, hook or
sandbox refuses an act, read [the refusal reference](references/refusal.md) before you go on.

## Do the due diligence first

Before you ask, check the facts within reach that are likely to change the answer: the history of the
same decision and what was tried before, the files and settings the answer touches, the project's
own rules, the read-only commands that settle a fact. Work out what each way forward leads to and
what its downside is, so the evidence chooses your recommendation.

## Write each brief

Write it in the order the person decides, so they know what is at stake before they meet your
pick:

- **The question**, after its id, in one line. It names the choice, not the answer you favour:
  one decision, in the person's words, asked so that each option answers it (a question that begins How should,
  Which or When). A yes-or-no question about your own pick leads the reader.
- **What waits on it** (`why_now`): the work the answer holds and the state it waits in, the side
  of the held act that is easiest to stay in, never half done. Say whether a default applies and
  when: a moment the person or the project already named (a handoff, a release, a date in the
  ticket or the grant). Where none exists, the work waits for the person, and that moment is one
  more question. Never invent a time limit.
- **The context** (`context`, `terms`): only what the person needs to judge: what the decision is
  about, what it touches, and how the mechanism works where that changes the choice. Make it easy
  to skim: a lead-in sentence, then a short list for parallel points; bold only the few words a
  skimmer needs; `code` for commands and paths. Define each term the person may not know. Leave
  out history they already know; background several briefs share goes once, above them.
- **A picture** (`diagram`, `picture`) where order, dependency, flow or before and after is the
  point, with a caption that says what to look at; never as decoration.
- **An offer to explore** (`explore`) when the decision is not simple: the options trade off
  things the person may value differently, turn on numbers they may want to try, or rest on a
  mechanism easier to see moving. Say what an interactive page would let them try; the command
  adds the reply that asks for it. A simple decision carries none.
- **Each credible way forward**, when there are two or more: what it leads to, when a reasonable
  person would choose it (`choose_if`: the condition, or what matters most to them), and its
  downside. Each is a way someone could sensibly pick; waiting is one where it is a real choice;
  no option is there to make another look good.
- **Your recommendation** (`recommend`, `recommend_way`), drawn on the option it names: why, the
  deciding factor, and what would change your mind.
- **At least one line of evidence**: what you checked, what you could not check (why, and what
  would settle it), or a fact.
- **Whether it can be undone.**

An emoji in your own text earns its place only where it says what a word would (❌ for missing),
never as decoration. A question in prose, a table of options, or a list without a recommendation
and an undo line is not a brief: the person cannot act on it in one reading.

When the person asks to explore a brief, build the page with the `explorable` skill: the brief
stays in the text, and the page's path goes beside it.

Give each brief an id no other session or record can take. Where the project's instructions keep one
numbering for briefs, take the next id from it; otherwise put your task's or worktree's name, in
letters, digits and hyphens, before the number (`fix-login-D1`), so that two sessions on one
machine, and the project's own decision numbers, never share an id. Cite a brief by that whole id
wherever it goes outside its document: a commit subject, a ticket, a handoff.

Explain every internal id or term in plain words where you use it, or leave it out. A step the
user types or checks by eye names a version, branch, tag or path, and a commit hash or digest only where
the check or the project's rule requires it. Claim no check that did not run: a verdict you give is your report of a command you ran.

## Draw it

With `outcomebound` on PATH, draw every brief: `outcomebound brief -` reads the JSON document
`outcomebound brief --help` describes from standard input, so drawing writes no file, and prints
it in the marks and diagram form the session's surface shows; `--help` names the surfaces that
need `--form mermaid`. Paste the complete rendered brief into the user-facing text as markdown,
never inside a code block. To revise it, change the input and draw it again; do not shorten or rewrite the rendered
brief. A refused brief is fixed and drawn again, never hand-written. Without `outcomebound` on PATH,
write the same shape by hand, options lettered.

The document is `{"briefs": [...], "order": [[before, after], ...]}`; every string is one line.
Each brief holds `id` (letters, digits, hyphens), `heading` (the question), `why_now`, `context`
(strings or lists of strings, none starting with a markdown mark), `terms` (`[term, meaning]`
pairs), `options` (objects with `way`, `leads_to`, `choose_if`, `downside`), `recommend` (why)
and `recommend_way` (the words of a way, never its letter), at least one of `checked`
(`{"verdicts": ["PASS"], "text": ...}`), `not_checked` or `facts`, and `undo`
(`{"can_be_undone": true, "text": ...}`); `diagram`, `picture` and `explore` where they help.
`outcomebound brief --help` gives each field's full rules; read it only when a draw is refused.

Several decisions go in one message; where one waits on another, the document's `order` draws
which comes first.

Where the harness asks the user through a question tool with choices to pick, read
[the question-tool reference](references/ask-tool.md).
