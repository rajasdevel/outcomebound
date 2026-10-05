# OutcomeBound is stdlib-only at runtime; tests need pytest (see requirements-dev.txt).
# Override PYTHON if your default `python3` lacks pytest, e.g.:
#   make test PYTHON=/path/to/python3
PYTHON ?= python3
# The parallel runner the uv fallback brings, pinned as in requirements-dev.txt.
PYTEST_VERSION ?= 9.1.1
XDIST_VERSION ?= 3.8.0

# The ref the floor's loosening check reads the change against: what it replaces.
OB_BASE ?= origin/main

.PHONY: test gate check scrub canary release-check
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

# The release canary: this checkout's engine beside the installed release, read-only, on each
# project of the local list that OB_CANARY_LIST names, under Python 3.10 and the installed
# release's Python. The list stays outside this repository, and the report names each project
# by its number. The verdict is recorded in the Git common directory for HEAD's tree; without
# the list, it reads UNVERIFIED and fails.
canary:
	$(PYTHON) scripts/canary.py

# Before a release is tagged: a PASS record of `make canary` exists for this tree, the release
# commit's version agrees everywhere (and with TAG, e.g. TAG=v1.0.0, once it is tagged), this
# repository's install is current, and gate, floor and suite pass on it. CI runs
# scripts/release-check.py on the tag, with no list, so the canary is checked only here.
release-check:
	$(PYTHON) scripts/canary.py --verify
	$(PYTHON) scripts/release-check.py $(if $(TAG),--tag $(TAG)) $(if $(CI_RUNS),--ci-runs $(CI_RUNS))
	scripts/outcomebound adopt . --check
	$(MAKE) check test
