---
id: tickets
family: setup
applies: projects that declare a ticket store
condition: when reading, working or changing this project's tickets or their declaration
detect: []
skills: ["slice-tickets", "hand-off-tickets"]
version: 8
---
**Context** — `.outcomebound/tickets.json` declares where this project's tickets live; the
engine reads them and reports, and writes nothing. How work lands here is what `CONTRIBUTING.md`
or `AGENTS.md` says, else what the goal envelope says; where none of them says, land it as local
commits on the current branch in the style the history shows, put how it should land in the
handover as a decision brief, and go on to the next ticket.
**Bounds** — a ticket's `bounds` are the paths its work may write. An edit outside them that the
work itself forces and that changes no behaviour of its own, such as an import, a registration, an
inventory, index or parity entry, or a test that asserts text the change moved, is the
implementer's: make it, name it in the handover, and ask nothing. An edit outside them that changes
behaviour, or in a path the project protects, is the person's: put it as a decision brief and go on
with what does not wait on it. An accepted ticket's title, body and decision keys are the user's,
and a body changes only on the person's word, so an edit outside `bounds` is named in the handover,
never written into the body; assigning it, commenting on it and closing it are the agent's. Push or
merge only where that is granted. A tracker is written to only where the declaration records that
grant, and otherwise the commands are printed for a person to run.
**Mechanisms** — `review` when how the work was sliced is a material blind spot; `spec` when a
decision something outside the slice relies on is missing.
**Completion bar** — `check` for a ticket's well-formedness; for its work, the `done-when` checks
run with each verdict reported, and passing at the project's own gate once the work lands there (a
ticket that waits on that gate is handed over, not waited on), and a handover the tracker shows, the
pull request or, where work lands with no pull request, the closing comment on the ticket, never
only a file the tracker cannot show, saying what changed, each check's verdict, what was decided
beyond the ticket, and the follow-ups found.
**Distinguish** — accepted ≠ assigned ≠ checks passing ≠ landed ≠ closed.
