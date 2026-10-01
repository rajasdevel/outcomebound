# OutcomeBound is stdlib-only at runtime; tests need pytest (see requirements-dev.txt).
# Override PYTHON if your default `python3` lacks pytest, e.g.:
#   make test PYTHON=/path/to/python3
PYTHON ?= python3
# The parallel runner the uv fallback brings, pinned as in requirements-dev.txt.
XDIST_VERSION ?= 3.8.0

# The ref the floor's loosening check reads the change against: what it replaces.
OB_BASE ?= origin/main

.PHONY: test gate check release-check
test:
	@if $(PYTHON) -m pytest --version >/dev/null 2>&1; then \
		if $(PYTHON) -c "import xdist" >/dev/null 2>&1; then $(PYTHON) -m pytest -n auto; \
		else $(PYTHON) -m pytest; fi; \
	elif command -v uv >/dev/null 2>&1; then \
		echo "pytest missing for $(PYTHON) (PEP 668 managed env) — falling back to uv"; \
		uv run --no-project --with pytest --with pytest-xdist==$(XDIST_VERSION) python -m pytest -n auto; \
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

# Before a release is tagged: the release commit's version agrees everywhere (and with TAG,
# e.g. TAG=v1.0.0, once it is tagged), this repository's install is current, and gate, floor
# and suite pass on it.
release-check:
	$(PYTHON) scripts/release-check.py $(if $(TAG),--tag $(TAG))
	scripts/outcomebound adopt . --check
	$(MAKE) check test
