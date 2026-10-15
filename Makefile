# OutcomeBound is stdlib-only at runtime; tests need pytest (see requirements-dev.txt).
# Override PYTHON if your default `python3` lacks pytest, e.g.:
#   make test PYTHON=/path/to/python3
PYTHON ?= python3
# The parallel runner the uv fallback brings, pinned as in requirements-dev.txt.
PYTEST_VERSION ?= 9.1.1
XDIST_VERSION ?= 3.8.0

# The ref the floor's loosening check reads the change against: what it replaces.
OB_BASE ?= origin/main

# Where `make kits` writes one <name>.zip and one <name>.md per kit under kits/.
KITS_OUT ?= dist/kits

.PHONY: python test gate check scrub canary release-check kits
# A $(PYTHON) that runs but is older than 3.10 stops every target here, by name, before a script
# fails on it with a raw error. One that is absent is left to fail in the recipe with make's own
# line. The message is the launcher's, so one phrase means one thing.
python:
	@if command -v $(PYTHON) >/dev/null 2>&1 && ! $(PYTHON) -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then \
		echo "outcomebound: no Python 3.10 or later: PYTHON=$(PYTHON) runs $$($(PYTHON) -V 2>&1) at $$(command -v $(PYTHON)); name one with PYTHON=/path/to/python3, or put one first on PATH" >&2; \
		exit 127; \
	fi
test gate check scrub canary release-check kits: python

test:
	@if $(PYTHON) -m pytest --version >/dev/null 2>&1; then \
		if $(PYTHON) -c "import xdist" >/dev/null 2>&1; then $(PYTHON) -m pytest -n auto; \
		else $(PYTHON) -m pytest; fi; \
	elif command -v uv >/dev/null 2>&1; then \
		echo "pytest missing for $(PYTHON) (PEP 668 managed env) — falling back to uv"; \
		uv run --no-project --with pytest==$(PYTEST_VERSION) --with pytest-xdist==$(XDIST_VERSION) python -m pytest -n auto; \
	else \
		echo "ERROR: no pytest for $(PYTHON) and no uv on PATH (see requirements-dev.txt)"; \
		exit 1; \
	fi
gate:
	$(PYTHON) scripts/check-no-deps.py

# This repository's quality floor, `.outcomebound/floor.json`: the project's own ruff,
# mypy and bash, run from the root. A missing or old tool reads UNVERIFIED, by name, and
# fails the check. The suite is `make test`, never a claim of the floor.
# Where $(PYTHON) lacks the floor's tools, as in a harness's hook that inherits no activated
# environment, the floor runs where uv installs requirements-dev.txt, pytest beside mypy.
check: gate
	@if $(PYTHON) -c "import pytest, mypy" >/dev/null 2>&1 || ! command -v uv >/dev/null 2>&1; then \
		scripts/outcomebound floor check . --base $(OB_BASE); \
	else \
		echo "floor tools missing for $(PYTHON) — running them through uv"; \
		uv run --no-project --quiet --with-requirements requirements-dev.txt \
			scripts/outcomebound floor check . --base $(OB_BASE); \
	fi

# The public-text check with the local list of private names that OB_SCRUB_LIST names, over
# the tracked files and the commit messages since OB_BASE. The list stays outside this
# repository; without it, the check reads UNVERIFIED and fails. `make check` runs the part
# that needs no list: home paths and email addresses.
scrub:
	$(PYTHON) scripts/check-public-text.py --private --base $(OB_BASE)

# Inspect custom commands as CONTRIBUTING.md requires before running the canary.
# The release canary: this checkout's engine beside the installed release on each
# project of the local list that OB_CANARY_LIST names, under Python 3.10 and the installed
# release's Python. The list stays outside this repository, and the report names each project
# by its number. The verdict is recorded in the Git common directory for HEAD's tree; without
# the list, it reads UNVERIFIED and fails.
canary:
	$(PYTHON) scripts/canary.py

# Before a release is tagged: a PASS record of `make canary` exists for this tree (a different
# tree fails there), the release commit's version agrees everywhere (and with TAG, e.g.
# TAG=v1.0.0, once it is tagged: annotated, on HEAD, with a passing CI run on main for HEAD),
# the package metadata and the workflow's PyPI job read right (from the files; PyPI itself is
# not called), `make scrub` passes with the list of private names, and this repository's install
# is current. Without TAG, gate, floor and suite run here as well. With TAG, they do not: the
# CI run on main for this exact commit runs the gate, the own-install check, the floor and the
# suite (the public-text list only where its secret is set, so scrub stays here). CI runs
# scripts/release-check.py once on the tag, with no list, so the canary is checked only here.
release-check:
	$(PYTHON) scripts/canary.py --verify
	$(PYTHON) scripts/release-check.py $(if $(TAG),--tag $(TAG)) $(if $(CI_RUNS),--ci-runs $(CI_RUNS))
	$(MAKE) scrub
	scripts/outcomebound adopt . --check
ifdef TAG
	@echo "gate, floor and suite: run by the CI run on main for $(TAG)'s commit, checked above"
else
	$(MAKE) check test
endif

# Each kit under kits/ (a SKILL.md a person pastes into their own assistant) packed as
# $(KITS_OUT)/<name>.zip, one entry, <name>/SKILL.md, and copied as $(KITS_OUT)/<name>.md, the
# two files a release attaches. Deterministic; standard library only.
kits:
	$(PYTHON) scripts/build-kits.py $(KITS_OUT)
