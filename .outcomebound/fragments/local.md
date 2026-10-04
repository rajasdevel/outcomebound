---
id: local
family: setup
applies: the OutcomeBound engine repository itself
edges: ["pushing a release tag"]
detect: []
version: 4
---
**Context** — this repository is both the contract and the engine that ships it, so an edit to
`OutcomeBound.md`, `templates/managed-block.agents.md.tmpl`, `skills/` or `fragments/` changes
what adopting projects load on their next install. Each area has one current design under
`docs/specs/`, edited in place: a shipped artifact that disagrees with it is the defect, unless
the decision itself changed, and then the design is edited in the same change.
**Bounds** — `outcomebound_tools/` and `scripts/` import the standard library only. Pushing a
release tag is an irreversible edge: a maintainer's act, or an agent's where a grant in
`.outcomebound/tag-grants.json` covers it. Released changelog sections are preserved history.
Text that leaves this machine (a commit message, a pull request, an issue, a changelog line, a
design, a shipped file) is public: it names no project that uses OutcomeBound, no person, no
local path, no id or role from a working file (a brief id, a review finding id, a stream, whose
ruling it was), and no count or anecdote from a private run; a behaviour is described in general
terms with a synthetic reproduction; a fact stands as fact only where a public source or a check
you ran shows it, else `UNVERIFIED`. A change lands only through a pull request, as
`CONTRIBUTING.md` "Agents and releases" says. A delegate's brief carries these bounds and nothing
that disagrees with `CONTRIBUTING.md`.
**Mechanisms** — `spec` when a wire format or block schema changes; `review` when a change alters
what the kernel, the contract, a skill, a fragment or a template tells a model to do, and when a
change adds an exemption to a gate or narrows what a gate counts (the floor, the instruction
audit, the finish check, a tickets refusal): that review tries to pass the gate without the ruling
it requires, and the pull request links it; `broad-suite` once at each landing, never inside a
delegate.
**Completion bar** — `make gate`, `make check` and `make test`, green at the tip that lands;
at a release, `make release-check` passes on the release commit. `make check` holds the
public-text claim, home paths, PASS or FAIL; `make scrub` adds the local list in `OB_SCRUB_LIST`,
PASS or FAIL with it and `UNVERIFIED` without it, before a pull request opens.
**Distinguish** — the template shipped ≠ the block installed in this repository's `AGENTS.md`;
committed ≠ pushed ≠ tagged ≠ adopted downstream.
