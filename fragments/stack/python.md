---
id: python
family: stack
applies: Python projects
detect: ["pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"]
version: 9
---
**Context** — Evidence is the actual interpreter, resolved dependencies and collected tests.
Where present, use the project's dependency records; a `pyproject.toml` version pin claims an environment, not its actual state.
**Bounds** — Preserve existing dependency selections and project-owned environment state; re-resolution is a deliberate scoped change.
Task-created disposable environments and caches may be cleaned within their ownership.
Where the project publishes, publishing to an index is an irreversible edge, declared by `ci-release` or this project's local fragment.
**Mechanisms** — When a focused regression adds useful signal, use `failing-test-first`.
When the changed module is imported across packages, use `broad-suite`.
**Completion bar** — Run affected project-native tests and existing static checks.
Before reading remaining lint findings, run the formatter and linter's own safe fix (`ruff format`, `ruff check --fix`, or the project's) on the paths you changed; read their diff.
Where a check runs only in a container or managed environment, run its floor claim there through its `prefix` and keep its baseline.
A Done command names the project's interpreter (`.venv/bin/python -m pytest`, or `uv run pytest` where `uv` is on the running process's PATH), never a tool held only in an activated environment: harness and CI processes may have none.
Until the package is imported in a clean interpreter, import-time behavior stays unverified.
**Distinguish** — edited ≠ tests collected ≠ passing ≠ installed in the target environment.
