#!/usr/bin/env bash
# Reference only. adopt never installs this; copy it into your CI yourself. Selection does not imply target wiring.
#
# usage: generic.sh [<base-ref>]   # the commit this change replaces; HEAD~1 without one
#
# For a CI system with no vendor-specific template alongside this one: call
# this from whatever your CI already runs -- a script step, a shell job, a
# task/tox/nox target.
# `outcomebound` must be on PATH: install it at a pinned release with
#   uv tool install "git+https://github.com/rajasdevel/outcomebound@v1.1.0"
# (or `pipx install` of the same, or `pip install` of it into a virtual
# environment), or link a checkout's scripts/outcomebound. If you install from a
# fork, change the URL to your fork's.
#
# Two lines, selected separately: the install check and the quality floor.
# Wire one or both, and delete the one you did not select.
set -euo pipefail

case "${1-}" in
-h | --help)
	echo "usage: generic.sh [<base-ref>]   # the commit this change replaces; HEAD~1 without one"
	exit 0
	;;
esac
base="${1:-HEAD~1}"

# --- 1. The install check ---------------------------------------------------

outcomebound adopt . --check

# --- 2. The quality floor ---------------------------------------------------
#
# Only for a project with a .outcomebound/floor.json, and AFTER the step that puts its
# tools on PATH: a missing or old tool makes its claim UNVERIFIED, which fails the
# check. The base is what the secrets scan and the loosening check read the change
# against.

outcomebound floor check . --base "$base"
