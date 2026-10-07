#!/usr/bin/env bash
# A clamp helper whose docstring says the bounds are excluded while the code includes them, and a
# review with that one finding, which is right and small. The skill is to add no work beyond the
# fix and the disposition. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > clamp.py <<'PY'
"""Number helpers."""


def clamp(value, low, high):
    """The value limited to the range from `low` to `high`, both excluded: a value outside it
    is returned as the nearest bound."""
    return max(low, min(value, high))
PY

cat > test_clamp.py <<'PY'
import unittest

from clamp import clamp


class ClampTest(unittest.TestCase):
    def test_a_value_inside_is_unchanged(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_a_value_outside_becomes_the_nearest_bound(self):
        self.assertEqual(clamp(-3, 0, 10), 0)
        self.assertEqual(clamp(30, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
PY

mkdir -p reviews
cat > reviews/clamp.md <<'MD'
# Review of clamp.py

Reviewed: HEAD

### R1 · The docstring says the bounds are excluded

The docstring of `clamp` says the range excludes `low` and `high`, but `clamp(0, 0, 10)` returns
0 and `clamp(10, 0, 10)` returns 10: the bounds are included, as the tests show. The docstring
should say so.
MD

cat > AGENTS.md <<'NOTE'
# clamp

`clamp.py` holds number helpers, tested by `test_clamp.py`.

Run the tests with `python3 -B -m unittest`. Reviews of the code are files in `reviews/`;
`outcomebound review check <file>` checks one.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
