# Lifecycle overlay: unattended-agents

A comparison for adoption. `adopt` never installs it, and the project owns every line it writes.
Propose a line below only where the project's committed text does not already lead an agent to the
decision the line changes; most lines are left out.

**Fits when** agents run without a person watching: on a schedule, in the background or from a
queue. It goes on any lifecycle.

**Fragments it would select:** none of its own; `workspace` and `multi-agent` stay with the facts
that select them.

**Scaffold set:** `+unattended-agents` adds the local line of
`templates/scaffold/unattended-agents/local.md`, and the platform act of an agent identity with a
scoped token and a log.

## Example lines

```text
Bounds: each agent works on its own branch or worktree and opens a pull request; it never approves
  or merges its own; it runs in the harness sandbox with network limits; it acts under its own
  identity with a scoped token, never an admin token.
```

## When to propose each line, and when to leave it out

- Propose the line whenever an agent runs unattended and the route does not already bound it.
- Leave it out where the project runs agents only in attended sessions.
