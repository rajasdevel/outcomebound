---
name: decision-brief
description: Use when a decision must go to the user — an act the agent's authority does not grant, such as an irreversible edge, an external write, spending or widening scope — or when a handoff leaves decisions to them. Covers the due diligence before asking and the brief's shape.
---

# Decision brief

Put each decision that is the user's so they can make it quickly and make it well. You are done
when each one is a drawn brief where the user will read it (the handoff, the goal's Progress
section, a comment on the ticket it holds, or your final message, when every remaining item waits
on an answer), and each reversible choice you made yourself is noted in one line where
the work is recorded. A link from that text to a file that holds the brief never stands in for
it: the brief itself is in the text.

## Decide what is yours

Decide every reversible choice inside your granted authority yourself. Ask the user only what is
theirs — an act your authority does not grant, such as an irreversible edge, an external write,
spending, or widening scope — batched into one message, and continue the work that does not wait
on the answer. A brief never ends your turn: a run starts without answers, and a brief holds only
the work that waits on it, so every other item goes on. Some harnesses honor authority only from
the user's own words: for an act a permission check guards, such as a deletion or a write outside
the project, the brief names the act so the user's reply can state it, not only a letter.

## Do the due diligence first

Before you ask, check everything within reach that could change the answer: read the files and the
history of what was tried before, run the read-only commands, look the fact up. Work out what each
way forward leads to and what its downside is, so the evidence chooses your recommendation.

## Write each brief

- an id and the question in one line;
- every way forward, when there are two or more, lettered A, B and on, each with what it leads to
  and its downside;
- your recommendation first, with why;
- at least one line of evidence: what you checked, what you could not check (why, and what
  would settle it), or a fact;
- whether it can be undone;
- what happens if no answer comes, and the state the held work waits in: the side of the held act
  that is easiest to stay in, never half done; give it as a `facts` pair labelled
  `If unanswered`;
- a diagram only when order, dependency, flow or before/after is the point.

Where the answer turns on values the person may judge differently from you, or on how the options
work in ways text compares poorly, also give them a decision explorable (the `explorable` skill):
the brief stays in the text, and the page's path goes beside it.

Give each brief an id no other session or record can take. Where the project's instructions keep one
numbering for briefs, take the next id from it; otherwise put your task's or worktree's name, in
letters, digits and hyphens, before the number (`fix-login-D1`), so that two sessions on one
machine, and the project's own decision numbers, never share an id. Cite a brief by that whole id
wherever it goes outside its document: a commit subject, a ticket, a handoff.

Explain every internal id or term in plain words where you use it, or leave it out. A step the
user types or checks by eye names a version, branch, tag or path, never a commit hash or other
digest. Claim no check that did not run: a verdict you give is your report of a command you ran.

## Draw it

With `outcomebound` on PATH, draw every brief: `outcomebound brief -` reads the JSON document
`outcomebound brief --help` describes from standard input, so drawing writes no file, and prints
it in the marks and diagram form the session's surface shows; `--help` names the surfaces that
need `--form mermaid`. Paste the complete rendered brief into the user-facing text as markdown,
never inside a code block. To revise it, change the input and draw it again; do not shorten or rewrite the rendered
brief. A refused brief is fixed and drawn again, never hand-written. Without `outcomebound` on PATH,
write the same shape by hand, options lettered.

A drawn brief, fenced here only to show its lines; its bare `D1` is right only where the
project's instructions number briefs:

````markdown
### D1 · Keep the old flag for one release?
- 👉 Recommend: A — two adopters still set it · confidence 80% (inferred)
- Options:
  - A keep it — adopters get a warning first
    - 🔻 Downside: one more release carries the old code path
  - B drop it now — the code path goes today
    - 🔻 Downside: an adopter who sets it is refused on upgrade
- ✅ Checked: `grep -r old_flag` finds two adopter configs
- If unanswered: the flag stays; only this item waits
- ↩️ Undo: revert the commit

How an upgrade reads the flag
```text
config --old_flag--> warning --> new flag
```
````

Several decisions go in one message; where one waits on another, the document's `order` draws
which comes first.

Where the harness asks the user through a question tool, with choices to pick, draw the brief in
your message first, then pipe the same document to `outcomebound brief --ask -` and ask with what it
prints, filling the tool's fields by name: its question or title, its header, and each option's
label and description, or its `line` where the tool takes options as plain strings. Never put a
drawn brief's lines into the tool's fields; the tool shows each field as one line. Where the tool
refuses the number of options a brief carries, or the brief has none and the tool needs some, the
drawn brief in your message is the ask: put no question for that brief, and the user answers in
words.
