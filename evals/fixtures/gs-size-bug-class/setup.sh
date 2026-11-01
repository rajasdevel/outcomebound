#!/usr/bin/env bash
# reportlib, a module of summaries for a weekly report. The module says that a summary of no data
# is None. Three summaries crash on an empty list; the person reports one of them.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p reportlib tests
printf '"""Helpers for the weekly report."""\n' > reportlib/__init__.py
cat > reportlib/summary.py <<'NOTE'
"""Summaries of a list of numbers, for the weekly report.

`average`, `median` and `value_range` summarise the values, and the report prints "n/a" where a
summary is None: a summary of an empty list is None. `total` and `count_over` are a sum and a
count, so they are 0 for an empty list.
"""


def total(values):
    return sum(values)


def count_over(values, limit):
    return sum(1 for value in values if value > limit)


def average(values):
    return sum(values) / len(values)


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def value_range(values):
    return max(values) - min(values)
NOTE
printf '' > tests/__init__.py
cat > tests/test_summary.py <<'NOTE'
import unittest

from reportlib.summary import average, count_over, median, total, value_range


class SummaryTest(unittest.TestCase):
    def test_total_and_count_over(self):
        self.assertEqual(total([1, 2, 3]), 6)
        self.assertEqual(count_over([1, 5, 9], 4), 2)

    def test_average(self):
        self.assertEqual(average([2, 4]), 3.0)

    def test_median_of_an_odd_and_an_even_list(self):
        self.assertEqual(median([3, 1, 2]), 2)
        self.assertEqual(median([1, 2, 3, 4]), 2.5)

    def test_value_range(self):
        self.assertEqual(value_range([4, 1, 9]), 8)


if __name__ == "__main__":
    unittest.main()
NOTE
cat > Makefile <<'NOTE'
.PHONY: test

test:
	python3 -B -m unittest discover -s tests -t . -q
NOTE
cat > AGENTS.md <<'NOTE'
# reportlib

Helpers for the weekly report, in `reportlib/`. Python standard library only.

Done: `make test`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +
field_close size.py
field_seed
