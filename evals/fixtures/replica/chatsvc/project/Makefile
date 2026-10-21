PYTHON ?= python3

.PHONY: check test test-unit test-integration docs-check serve

# Static checks: the settings and limits load, everything compiles, the docs hold.
check: docs-check
	$(PYTHON) -B -c "from chatsvc import config, limits; s = config.load('config'); limits.load(s.limits_path)"
	$(PYTHON) -m compileall -q chatsvc fakeprovider scripts tests > /dev/null

docs-check:
	$(PYTHON) -B scripts/docs_check.py

# The full suite: unit tests, then the integration suite (about a minute and a half).
test: test-unit test-integration

test-unit:
	$(PYTHON) -B -m unittest discover -s tests -q

test-integration:
	$(PYTHON) -B tests/integration/run.py

serve:
	$(PYTHON) -m chatsvc
