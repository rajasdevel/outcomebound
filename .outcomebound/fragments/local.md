---
id: local
family: setup
applies: the OutcomeBound engine repository itself
edges: ["pushing a release tag"]
detect: []
version: 3
---
**Context** — this repository is both the contract and the engine that ships it, so an edit to
`OutcomeBound.md`, `templates/managed-block.agents.md.tmpl`, `skills/` or `fragments/` changes
what adopting projects load on their next install. Each area has one current design under
`docs/specs/`, edited in place: a shipped artifact that disagrees with it is the defect, unless
the decision itself changed, and then the design is edited in the same change.
**Bounds** — `outcomebound_tools/` and `scripts/` import the standard library only. Pushing a
release tag is an irreversible edge: a maintainer's act, or an agent's where a grant in
`.outcomebound/tag-grants.json` covers it. Released changelog sections are preserved history.
**Mechanisms** — `spec` when a wire format or block schema changes; `review` when a change alters
what the kernel, the contract or the core skill tells a model to do; `broad-suite` once at each
landing, never inside a delegate.
**Completion bar** — `make gate`, `make check` and `make test`, green at the tip that lands;
at a release, `make release-check` passes on the release commit.
**Distinguish** — the template shipped ≠ the block installed in this repository's `AGENTS.md`;
committed ≠ pushed ≠ tagged ≠ adopted downstream.
