# Designs

One current design per area, edited in place; Git holds every earlier version, and the commit
that changes a decision says why. A design stays within 1,500 words and names no model or
vendor. The Owner column holds `user` or `agent`: whose decision the row is.

- [install](install/design.md) — `outcomebound adopt`: install, upgrade, check and remove.
- [distribution](distribution/design.md) — how `outcomebound` reaches an adopter: the package, its build and the launcher.
- [skills](skills/design.md) — which skills ship, to whom, and the bar each meets.
- [floor](floor/design.md) — the quality floor, `outcomebound floor`.
- [tickets](tickets/design.md) — the ticket layer, `outcomebound tickets`.
- [decision-brief](decision-brief/design.md) — how a decision is put to a person, `outcomebound brief`.
- [instructions](instructions/design.md) — read-only checks on a project's instruction files, `outcomebound instructions`.
- [finish-check](finish-check/design.md) — at the stop hook of `claude-code` and `codex`, the recorded Done commands run, and a failure goes back to the agent; `outcomebound finish-check`.
- [research](research/design.md) — the research repository: how the engine finds, prints and updates its clone, and takes findings back.

Drafts, marked `status: draft`, say at their top what landing them takes, and none of the rules
above holds one until it lands.

`bash scripts/new-spec.sh <slug>` scaffolds a new design from `templates/spec/design.md`;
`--with-plan` adds `templates/spec/plan.md` as well, for work whose sequencing or resumption
needs a plan.
