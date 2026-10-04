---
id: solo
family: setup
applies: single-maintainer repositories
condition: when deciding who reviews or verifies a change, or before unattended work
detect: []
version: 5
---
**Context** — a single maintainer does not imply a standing second human reviewer. Available
reviewers, checks, runtime observations, and user feedback are distinct sources of evidence.
**Bounds** — authority comes from the task, project, and relevant external boundary; maintaining
the repository does not grant every permission. Unattended work stays within those bounds and
does not wait on the maintainer inside them: decide what they let you decide, record each such
choice, and batch the maintainer's decisions for the handoff while the work that does not depend
on them goes on.
**Mechanisms** — `failing-test-first` where a regression would go unnoticed for weeks.
**Completion bar** — the checks the maintainer will actually rerun; a check nobody runs is not a
completion bar.
**Distinguish** — the maintainer decided ≠ the maintainer verified ≠ a check enforces it.
