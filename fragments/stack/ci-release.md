---
id: ci-release
family: stack
applies: repositories that version, tag, and publish releases
condition: before a release, a tag push or a publish
edges: ["pushing a tag", "publishing a package", "moving a shared registry tag", "editing a published release"]
detect: ["VERSION", ".github/workflows/release*.yml", ".github/workflows/release*.yaml", ".github/workflows/publish*.yml", ".github/workflows/publish*.yaml"]
version: 8
---
**Context** — a workflow file is a claim; the run log and the published artifact are the
evidence. Version, changelog entry, and tag must agree with what was actually built.
**Bounds** — pushing a tag, publishing a package, moving a shared registry tag, and editing a
published release are irreversible edges; a merge grant is not a tag grant; released changelog
sections are preserved history.
Consumers or adopters of a release move within a window the project states, or the hold is recorded
with its owner; where the project states neither, report the gap and do not set a window yourself.
**Mechanisms** — `policy-gate` before any publish or tag push; `spec` when the release contract
or compatibility window changes; `broad-suite` before integrating a release candidate;
`runtime-check` after a publish, when only the live registry settles whether it served. The static
check is best a checked-in script that fails unless the tag, the version and the changelog heading
agree.
**Completion bar** — version, changelog entry, and tag name agree (static); the tagged commit is on
the default branch; the candidate is proven before the release commit, and a release commit that
only sets the version, the changelog and the pins needs the static check, not a second proof; the
release workflow, where the project has one, is green on the exact commit (build); the published
artifact stays unverified until it is resolved from the registry, a read you can make yourself.
**Distinguish** — committed ≠ pushed ≠ CI green ≠ tagged ≠ released.
