PYTHON ?= python3

.PHONY: test check

# The unit tests.
test:
	$(PYTHON) -B -m unittest discover -s tests

# What CI runs on every pull request: the tests, and the release-notes check.
check: test
	$(PYTHON) scripts/release_notes.py --check
