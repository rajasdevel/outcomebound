---
id: multi-agent
family: stack
applies: repositories where work is delegated to subagents or parallel workers
condition: when delegating to a subagent or integrating a delegate's work
detect: [".claude/agents/*.md", ".codex/agents/*.md", ".agents/*.md"]
version: 8
---
**Context** — a delegate's report is a claim; the worktree diff, the check output, and the files
it actually touched are the evidence. The orchestrator's context is not shared state.
**Bounds** — a dispatch names the model and effort it chose, set with the tool's own parameter where it has one, and inheriting the session's is a
choice to name, since a harness default can be the session's model. The bounds are written in the
brief itself, since a delegate may load no project instructions. Each delegate owns explicit
paths; the integration commit, the shared branch, and any effect outside a delegate's paths
belong to the orchestrator. Another worker's worktree is preserved state.
**Mechanisms** — `review` when a miss would reach users and no check the orchestrator can run would catch it;
overlapping edits need orchestrator reconciliation and affected checks. Use `broad-suite` once at
each integration rather than inside every delegate; `goal-envelope` when a delegate runs unattended
across sessions.
**Completion bar** — the orchestrator verifies reported diffs and check evidence; re-run affected
checks when their inputs or integration context changed. Human observations remain separately attributed.
A delegate that reports itself blocked is recorded with its reason, and the work that does not
depend on it goes on. Where every remaining item waits on a delegate that is still running, wait
once for its report the way the harness waits (one wait with no deadline, or the turn's end where
the harness wakes you on the report); never a loop of short waits or status reads. A worker holds
one role at a time, and the tickets of one landing.
**Distinguish** — a delegate reported ≠ the orchestrator verified ≠ integrated ≠ merged.
