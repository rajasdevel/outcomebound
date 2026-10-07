#!/usr/bin/env bash
# Explanation-only work where accepted design and code disagree at a disclosed boundary.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"
mkdir -p tests docs/specs/packing
cp "$here/design.md" docs/specs/packing/design.md
cat > packing.py <<'PY'
def carton_for(weight_g):
    return "small" if weight_g < 500 else "large"
PY
cat > tests/test_packing.py <<'PY'
import unittest
from packing import carton_for


class CartonTest(unittest.TestCase):
    def test_499_grams(self):
        self.assertEqual(carton_for(499), "small")

    def test_501_grams(self):
        self.assertEqual(carton_for(501), "large")
PY
cat > AGENTS.md <<'NOTE'
# packing

`packing.py` selects a carton. Its accepted design is `docs/specs/packing/design.md`.
Run the tests with `python3 -B -m unittest discover -s tests`.
Keep working notes under `.agents/work/`.
Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
. "$here/../skills-close/close.sh"
