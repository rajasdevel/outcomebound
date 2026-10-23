PYTHON ?= python3

.PHONY: build check

# Build site/ from content/.
build:
	$(PYTHON) build.py

# What CI runs: site/ must be what content/ builds, and every link must work.
check:
	$(PYTHON) build.py --check
