---
id: multi-agent
family: stack
applies: repositories where work is delegated to subagents or parallel workers
condition: when delegating to a subagent or integrating a delegate's work
detect: [".claude/agents/*.md", ".codex/agents/*.md", ".agents/*.md"]
version: 4
---
**Context** — a delegate's report is a claim; the worktree diff, the check output, and the files
it actually touched are the evidence. The orchestrator's context is not shared state.
**Bounds** — each delegate owns explicit paths; the integration commit, the shared branch, and
any effect outside a delegate's paths belong to the orchestrator. Another worker's worktree is
preserved state.
**Mechanisms** — `review` when a miss would reach users and no check the orchestrator can run would catch it;
overlapping edits need orchestrator reconciliation and affected checks. Use `broad-suite` once at
integration rather than inside every delegate; `goal-envelope` when a delegate runs unattended
across sessions.
**Completion bar** — the orchestrator verifies reported diffs and check evidence; re-run affected
checks when their inputs or integration context changed. Human observations remain separately attributed.
**Distinguish** — a delegate reported ≠ the orchestrator verified ≠ integrated ≠ merged.
