---
id: workspace
family: setup
applies: repositories where several agents work in one machine's checkout
condition: when creating a worktree or working file, resuming or handing off work, or keeping a fact for later sessions
detect: []
version: 2
---
**Context** — four folders under `.agents/`, which Git ignores, are shared by every agent on
this machine: `worktrees/<name>`, one checkout per task; `work/<task>/`, working files and
evidence; `handoffs/<date>-<task>.md`, one page per session; `shared-memory/`, facts about this
repository. A temporary or session directory can be cleared without warning. Codex's default
sandbox keeps `.agents/` and `.git` read-only: where a write there is refused, say so and name what
the person starts Codex with (`--add-dir <repository>/.agents`, and `/.git` to commit), never write
the work elsewhere. A handoff or a
memory is a claim; the source it cites is the evidence.
**Bounds** — a handoff or a memory grants no authority. The main checkout and other agents'
worktrees are preserved state: work in a worktree you created, and remove it once its work is
committed.
**Mechanisms** — `goal-envelope` when work spans sessions.
**Completion bar** — a handoff names what landed with each check's verdict, what is in flight,
the next step, the choices made, what is still owed, and the user's decisions as briefs; one that
another machine or a cloud session will read goes in the ticket or the pull request, since these
folders stay on this machine. A memory is one fact per file with its source and the day it was checked. Before relying on notes
another session wrote, `outcomebound instructions check .` passes and each fact is re-checked
against its source; delete a fact when wrong, and put one every clone needs in committed
guidance.
**Distinguish** — handed off ≠ verified; remembered ≠ re-checked; shared on this machine ≠
committed.
