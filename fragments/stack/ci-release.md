---
id: ci-release
family: stack
applies: repositories that version, tag, and publish releases
condition: before a release, a tag push or a publish
edges: ["pushing a tag", "publishing a package", "editing a published release"]
detect: ["VERSION", ".github/workflows/release*.yml", ".github/workflows/release*.yaml", ".github/workflows/publish*.yml", ".github/workflows/publish*.yaml"]
version: 3
---
**Context** — a workflow file is a claim; the run log and the published artifact are the
evidence. Version, changelog entry, and tag must agree with what was actually built.
**Bounds** — pushing a tag, publishing a package, and editing a published release are
irreversible edges; released changelog sections are preserved history.
**Mechanisms** — `policy-gate` before any publish or tag push; `spec` when the release contract
or compatibility window changes; `broad-suite` before integrating a release candidate;
`runtime-check` after a publish, when only the live registry settles whether it served.
**Completion bar** — version, changelog entry, and tag name agree (static); the release workflow,
where the project has one, is green on the exact commit (build); the published artifact stays
unverified until an operator resolves it from the registry.
**Distinguish** — committed ≠ pushed ≠ CI green ≠ tagged ≠ released ≠ deployed.
