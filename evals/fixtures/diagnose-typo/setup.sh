#!/usr/bin/env bash
# A mean helper with a misspelt variable that its test run reports as a NameError naming the
# line. The cause is plain in the error. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > tally.py <<'PY'
"""Small statistics helpers."""


def mean(values):
    """The arithmetic mean of a non-empty list of numbers."""
    total = sum(values)
    return totl / len(values)
PY

cat > test_tally.py <<'PY'
import unittest

from tally import mean


class MeanTest(unittest.TestCase):
    def test_the_mean_of_three_numbers(self):
        self.assertEqual(mean([2, 4, 9]), 5)

    def test_the_mean_of_one_number_is_that_number(self):
        self.assertEqual(mean([7]), 7)


if __name__ == "__main__":
    unittest.main()
PY

cat > AGENTS.md <<'NOTE'
# tally

`tally.py` holds small statistics helpers, tested by `test_tally.py`.

Run the tests with `python3 -B -m unittest`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
