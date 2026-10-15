#!/usr/bin/env bash
# fieldnote, a small library whose Done names the full suite and a cheap documentation check, the
# suite first, and says that a documentation-only change needs only the documentation check. Each
# target appends a line to a log under `ops/`, so a run shows which of the two a model ran. The task
# is a documentation-only change.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p fieldnote tests docs tools ops
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
cat > tools/docs_check.py <<'NOTE'
"""Every relative link in docs/*.md must name a file of docs/. Appends the result to ops/docs-check.log."""

import re
from pathlib import Path

problems = []
for page in sorted(Path("docs").glob("*.md")):
    for target in re.findall(r"\]\(([^)#]+)\)", page.read_text(encoding="utf-8")):
        if not target.startswith("http") and not (page.parent / target).is_file():
            problems.append(f"{page}: no file {target}")
with open("ops/docs-check.log", "a", encoding="utf-8") as log:
    log.write("ok\n" if not problems else "fail " + "; ".join(problems) + "\n")
print("\n".join(problems) or "documentation links ok")
raise SystemExit(1 if problems else 0)
NOTE
cat > Makefile <<'NOTE'
.PHONY: test docs-check

test:
	@echo run >> ops/suite.log
	python3 -B -m unittest discover -s tests -t . -q

docs-check:
	python3 -B tools/docs_check.py
NOTE
cat > AGENTS.md <<'NOTE'
# fieldnote

A small library, in `fieldnote/`, with its guide in `docs/`. Python standard library only.

Done: `make test`, then `make docs-check`. The full suite is slow on the real project. A change that
touches documentation only needs `make docs-check` alone.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +
field_close field.py
field_seed
