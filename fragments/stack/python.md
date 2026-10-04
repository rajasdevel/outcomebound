---
id: python
family: stack
applies: Python projects
condition: when choosing the checks for a Python change, or changing its dependencies or environment
detect: ["pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"]
version: 5
---
**Context** — the actual interpreter, resolved dependencies, and collected tests are the
evidence. Use the project's dependency records when present; a version pin in `pyproject.toml`
is a claim about the environment, not the environment.
**Bounds** — preserve existing dependency selections and project-owned environment state;
re-resolution is a deliberate scoped change. Task-created disposable environments and caches
can be cleaned within their ownership. Where the project publishes, publishing to an index is an
irreversible edge, which the `ci-release` fragment, or this project's local fragment, declares.
**Mechanisms** — `failing-test-first` when a focused regression adds useful signal;
`broad-suite` when the changed module is imported across packages.
**Completion bar** — the affected project-native tests and existing static checks;
import-time behavior stays unverified until the
package is imported in a clean interpreter.
**Distinguish** — edited ≠ tests collected ≠ passing ≠ installed in the target environment.
