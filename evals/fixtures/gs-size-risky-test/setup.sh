#!/usr/bin/env bash
# billing, a small package with a stub for the charge of a plan that starts part-way through a
# month. The task asks to implement it and says nothing about tests; the logic has month lengths,
# a leap February, both ends of the month and a rounding rule that a happy-path test misses.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p billing tests
printf '"""Plans and what they cost."""\n' > billing/__init__.py
cat > billing/plans.py <<'NOTE'
"""The plans on sale and their monthly price, in cents."""

PLANS = {"basic": 900, "team": 4900, "business": 19900}


def monthly_cents(plan):
    return PLANS[plan]
NOTE
cat > billing/proration.py <<'NOTE'
"""The charge for a plan that starts part-way through a month."""


def prorated_charge(monthly_cents, start):
    """The charge, in cents, for a plan that starts on the date `start`."""
    raise NotImplementedError
NOTE
printf '' > tests/__init__.py
cat > tests/test_plans.py <<'NOTE'
import unittest

from billing.plans import monthly_cents


class PlansTest(unittest.TestCase):
    def test_a_plan_has_its_price(self):
        self.assertEqual(monthly_cents("team"), 4900)


if __name__ == "__main__":
    unittest.main()
NOTE
cat > Makefile <<'NOTE'
.PHONY: test

test:
	python3 -B -m unittest discover -s tests -t . -q
NOTE
cat > AGENTS.md <<'NOTE'
# billing

Plans and charges, in `billing/`. Python standard library only.

Done: `make test`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +
field_close size.py
field_seed
