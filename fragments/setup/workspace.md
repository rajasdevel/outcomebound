---
id: workspace
family: setup
applies: repositories where agents run commands in one machine's checkout, and several agents or sessions share it
condition: when creating a worktree or working file, running a command whose output you read, resuming or handing off work, or keeping a fact for later sessions
detect: [".agents/worktrees", ".agents/work", ".agents/handoffs", ".agents/shared-memory"]
version: 3
---
**Context** — four folders under `.agents/`, which Git ignores, are shared by every agent on
this machine: `worktrees/<name>`, one checkout per task; `work/<task>/`, working files and
evidence; `handoffs/<date>-<task>.md`, one page per session; `shared-memory/`, facts about this
repository. A temporary or session directory can be cleared without warning. Codex's default
sandbox keeps `.agents/` and `.git` read-only: where a write there is refused, say so and name what
the person starts Codex with (`--add-dir <repository>/.agents`, and `/.git` to commit), never write
the work elsewhere. A handoff or a
memory is a claim; the source it cites is the evidence. Commands: a harness may give a command a terminal, and all it prints is context spent; take
quiet from a tool's own flags, never from hiding an error or a check. A pager waits for a key:
`git --no-pager`, a tool's `--no-pager`, else `PAGER=cat`. An editor waits: `git commit -m`,
`--no-edit`, `GIT_EDITOR=true git rebase --continue`. A prompt must fail with its reason:
`GIT_TERMINAL_PROMPT=0` for git remotes, `ssh -o BatchMode=yes -o ConnectTimeout=10 -o
LogLevel=ERROR` (never `-q`), `sudo -n`. Stdin may never close: `< /dev/null` where no input is
meant (`codex exec`, `ssh` in a loop). Follow, watch and server commands never exit: bound them or
run them in the background; tests run once. Bound output at its source (`-n`, `--stat`, `rg -m`);
send long output to `work/<task>/`, then read its tail and exit code (`| tail` reports tail's);
`curl -fsS`, never `-s` alone.
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
