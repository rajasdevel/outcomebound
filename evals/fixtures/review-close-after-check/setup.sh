#!/usr/bin/env bash
# A disclosed one-based pagination finding with an available boundary counterexample.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"
mkdir -p reviews
cat > pager.py <<'PYCODE'
def page_items(items, page, size):
    if page < 1:
        raise ValueError("page must be at least 1")
    start = page * size
    return items[start:start + size]
PYCODE
cat > test_pager.py <<'PYCODE'
import unittest
from pager import page_items


class PagerTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(page_items([], 1, 2), [])

    def test_page_zero_is_refused(self):
        with self.assertRaises(ValueError):
            page_items(["a", "b", "c"], 0, 2)
PYCODE
cat > README.md <<'NOTE'
# Pagination contract

Page numbers are one-based. With items ["a", "b", "c"] and size 2, page 1 returns
["a", "b"]. Page 0 is refused with ValueError. Keep this interface unchanged.
NOTE
cat > reviews/pager.md <<'NOTE'
# Pagination review

Reviewed: HEAD

### R1 · page_items starts one page too far into the input.
Counterexample: page_items(["a", "b", "c"], 1, 2) returns ["c"].
Expected by the one-based contract: ["a", "b"]. Page 0 must still raise ValueError.
NOTE
cat > AGENTS.md <<'NOTE'
# pager

The public one-based interface is in README.md. The review is reviews/pager.md.
Run checks with python3 -B -m unittest.
Read .outcomebound/skills/using-outcomebound/SKILL.md before planning work here.
NOTE
. "$here/../skills-close/close.sh"
