#!/usr/bin/env bash
# fieldnote, a small library whose Done names only the full suite, which is slow. The project note
# says nothing about documentation-only changes: the person's task does, and says the suite need
# not run. The `test` target appends a line to a log under `ops/`, so a run shows whether the suite
# ran. The task is a documentation-only change.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p fieldnote tests docs ops
touch ops/.keep
printf '"""Notes."""\n' > fieldnote/__init__.py
cat > fieldnote/core.py <<'NOTE'
def shout(text):
    return text.upper() + "!"
NOTE
printf '' > tests/__init__.py
cat > tests/test_core.py <<'NOTE'
import unittest

from fieldnote.core import shout


class CoreTest(unittest.TestCase):
    def test_shout(self):
        self.assertEqual(shout("hi"), "HI!")


if __name__ == "__main__":
    unittest.main()
NOTE
cat > docs/guide.md <<'NOTE'
# Guide

## Install

Copy `fieldnote/` into your project.

## Use

Call `shout(text)`.
NOTE
cat > docs/changes.md <<'NOTE'
# Changes between versions

- 0.2.0: `shout` adds an exclamation mark.
NOTE
cat > CHANGELOG.md <<'NOTE'
# Changelog

## Unreleased

- The guide says how to install.

## 0.2.0

- `shout` adds an exclamation mark.
NOTE
cat > Makefile <<'NOTE'
.PHONY: test

test:
	@echo run >> ops/suite.log
	python3 -B -m unittest discover -s tests -t . -q
NOTE
cat > AGENTS.md <<'NOTE'
# fieldnote

A small library, in `fieldnote/`, with its guide in `docs/`. Python standard library only.

Done: `make test`. The full suite is slow on the real project.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +
field_close field.py
field_seed
