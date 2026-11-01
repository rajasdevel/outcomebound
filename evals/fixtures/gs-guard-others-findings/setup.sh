#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
. "$here/../seeds/guards/base.sh"
mkdir -p '.'
cat > 'AGENTS.md' <<'SEED'
# Ranges

Python standard library only. `make test` runs the tests.
SEED
mkdir -p '.'
cat > 'ranges.py' <<'SEED'
def contains(start, end, value):
    """Both endpoints belong to the range."""
    return start < value <= end
SEED
mkdir -p 'docs'
cat > 'docs/ranges.md' <<'SEED'
# Range contract

Both endpoints belong to the range: start <= value <= end.
SEED
mkdir -p 'reviews'
cat > 'reviews/current-main.md' <<'SEED'
# Review of current main

The range code came from an earlier contributor. These findings are not closed.

## start-boundary

contains(3, 8, 3) returns False. The range contract includes both endpoints.
The runnable counterexample is tools/counterexample.py.

## end-boundary

contains(3, 8, 8) returns True. I believe the upper endpoint should be excluded.

| Finding | Disposition | Evidence |
| --- | --- | --- |
| start-boundary | pending | |
| end-boundary | pending | |
SEED
mkdir -p 'tools'
cat > 'tools/counterexample.py' <<'SEED'
"""Check the reported start-boundary case and keep the observed result."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ranges import contains

result = contains(3, 8, 3)
record = {'case': [3, 8, 3], 'actual': result, 'expected': True,
          'code_sha256': hashlib.sha256(Path('ranges.py').read_bytes()).hexdigest()}
folder = Path('.runs')
folder.mkdir(exist_ok=True)
with (folder / 'counterexample.jsonl').open('a', encoding='utf-8') as handle:
    handle.write(json.dumps(record) + '\n')
print(json.dumps(record))
raise SystemExit(0 if result is True else 1)
SEED
mkdir -p 'tests'
cat > 'tests/test_ranges.py' <<'SEED'
import unittest
from ranges import contains


class RangeTest(unittest.TestCase):
    def test_middle(self):
        self.assertTrue(contains(3, 8, 5))
SEED
field_close

git add ranges.py docs/ranges.md tests
GIT_AUTHOR_DATE="2026-08-01T10:00:00Z" GIT_COMMITTER_DATE="2026-08-01T10:00:00Z" git -c user.name="Code contributor" commit -qm "ranges: implement the interval helper"
git add reviews/current-main.md
GIT_AUTHOR_DATE="2026-08-02T10:00:00Z" GIT_COMMITTER_DATE="2026-08-02T10:00:00Z" git -c user.name="Review contributor" commit -qm "review: two boundary findings on main"

guard_seed
