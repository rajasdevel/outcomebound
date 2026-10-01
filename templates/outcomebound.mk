# Optional Make conveniences for a repository OutcomeBound is installed in.
# Include with: include outcomebound.mk

# `outcomebound` on PATH: installed from a release, or a checkout's scripts/outcomebound.
OB_ENGINE ?= outcomebound
# The ref the floor's loosening check reads the change against.
OB_BASE ?= origin/main

.PHONY: ob-validate ob-floor-check ob-floor-ratchet

ob-validate:
	@test -n "$(PLAN)" || { echo "usage: make ob-validate PLAN=<validation.json>" >&2; exit 2; }
	$(OB_ENGINE) validation "$(PLAN)"

# Every claim of .outcomebound/floor.json, and the loosening check against OB_BASE.
ob-floor-check:
	$(OB_ENGINE) floor check . --base "$(OB_BASE)"

# Delete the baseline lines no finding matches: a tightening, so it asks nothing.
ob-floor-ratchet:
	$(OB_ENGINE) floor ratchet .
