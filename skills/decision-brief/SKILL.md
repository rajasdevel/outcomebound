---
name: decision-brief
description: Use when a decision must go to the user — an act your authority does not grant, such as an irreversible edge, an external write, spending or widening scope — or when a handoff leaves decisions to them. Covers the due diligence before asking and the brief's shape.
---

# Decision brief

Put each decision that is the user's so they can make it quickly and make it well. You are done
when each one is a drawn brief in the message that reaches the user (the turn's final message,
the handoff, or the tracker comment), and each reversible choice you made yourself is noted in
one line where the work is recorded.

## Decide what is yours

Decide every reversible choice inside your granted authority yourself. Ask the user only what is
theirs — an act your authority does not grant, such as an irreversible edge, an external write,
spending, or widening scope — batched into one message when the work reaches it, and continue the
work that does not wait on the answer. Some harnesses honor authority only from the user's own
words: for an act a permission check guards, such as a deletion or a write outside the project,
the brief names the act so the user's reply can state it, not only a letter.

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
- a diagram only when order, dependency, flow or before/after is the point.

Explain every internal id or term in plain words where you use it, or leave it out. A step the
user types or checks by eye names a version, branch, tag or path, never a commit hash or other
digest. Claim no check that did not run: a verdict you give is your report of a command you ran.

## Draw it

With `outcomebound` on PATH, draw every brief: `outcomebound brief -` reads the JSON document
`outcomebound brief --help` describes from standard input, so drawing writes no file, and prints
it in the marks and diagram form the session's surface shows; `--help` names the surfaces that
need `--form mermaid`. Show its output as markdown, never inside a code block. A brief the
command refuses is fixed and drawn again, never hand-written. Without `outcomebound` on PATH,
write the same shape by hand, options lettered.

A drawn brief, fenced here only to show its lines:

````markdown
### D1 · Keep the old flag for one release?
- 👉 Recommend: A — two adopters still set it · confidence 80% (inferred)
- Options:
  - A keep it — adopters get a warning first
    - 🔻 Downside: one more release carries the old code path
  - B drop it now — the code path goes today
    - 🔻 Downside: an adopter who sets it is refused on upgrade
- ✅ Checked: `grep -r old_flag` finds two adopter configs
- ↩️ Undo: revert the commit

How an upgrade reads the flag
```text
config --old_flag--> warning --> new flag
```
````

Several decisions go in one message; where one waits on another, the document's `order` draws
which comes first.
