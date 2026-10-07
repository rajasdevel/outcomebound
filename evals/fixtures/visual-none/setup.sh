#!/usr/bin/env bash
# A prices module with one helper, and a plain text request that holds no picture. The skill's
# paragraph on pictures is to add nothing here. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > prices.py <<'PY'
"""Prices the site prints."""


def format_price(cents):
    """`cents` as dollars with two decimals: `1200` is `$12.00`."""
    return f"${cents // 100}.{cents % 100:02d}"
PY

cat > test_prices.py <<'PY'
import unittest

from prices import format_price


class FormatPriceTest(unittest.TestCase):
    def test_whole_dollars(self):
        self.assertEqual(format_price(1200), "$12.00")

    def test_cents_are_padded(self):
        self.assertEqual(format_price(5), "$0.05")


if __name__ == "__main__":
    unittest.main()
PY

cat > AGENTS.md <<'NOTE'
# prices

`prices.py` holds the prices the site prints, tested by `test_prices.py`.

Run the tests with `python3 -B -m unittest`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
