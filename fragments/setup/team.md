---
id: team
family: setup
applies: repositories with code owners, branch protection, or required review
condition: when a change needs review, crosses code owners or reaches a protected branch
detect: ["CODEOWNERS", ".github/CODEOWNERS"]
version: 4
---
**Context** — current ownership and protection settings identify configured review requirements.
Local checks, CI runs, and owner approvals are distinct evidence; none implies the others.
**Bounds** — the task defines owned scope; cross-owner work preserves the project's coordination
requirements. Shared branch history and configured protections are preserved state.
**Mechanisms** — `review` when existing owner policy requires it; `policy-gate` at the project's
configured protected boundary, not one you author; `spec` when another owner's later work relies
on a decision the code cannot show.
**Completion bar** — the affected project checks, plus configured status checks and approvals at
the boundary where they apply. Use the project's chosen handoff surface to record the evidence.
**Distinguish** — locally green ≠ CI green ≠ approved ≠ merged.
