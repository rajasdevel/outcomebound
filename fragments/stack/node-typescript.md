---
id: node-typescript
family: stack
applies: Node.js and TypeScript projects
condition: when choosing the checks for a Node.js or TypeScript change, or changing its dependencies
detect: ["package.json", "tsconfig.json", "pnpm-lock.yaml", "package-lock.json"]
version: 5
---
**Context** — resolved dependencies and the configured tools' output are evidence. Use a lockfile
when present; type-checking, runtime tests, and an emitted bundle establish different properties.
**Bounds** — existing dependency selections are preserved and changed deliberately; where the
project publishes, publishing a package version and moving a shared registry tag are irreversible
edges, which the `ci-release` fragment declares.
**Mechanisms** — `failing-test-first` when a focused regression adds useful signal; `broad-suite`
when shared changes affect consumers; `spec` when later work relies on an API or wire-format
decision the code cannot show; `review` when existing ownership policy requires it.
**Completion bar** — affected tests and configured type/build checks for the changed package and
its consumers. Required missing checks remain unverified; plain JavaScript or source-published
packages do not imply a compiler or bundler. User-visible behavior needs a relevant runtime observation.
**Distinguish** — type-checked ≠ tested ≠ built ≠ published.
