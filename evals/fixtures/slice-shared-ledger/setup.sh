#!/usr/bin/env bash
# An expenses package with a status table every change updates, a short design of two
# unrelated changes that each set their own row of that table, two implementers working at the
# same time, a declared ticket store and claims plan, and the project's ticket template. With
# the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

mkdir -p expenses tests docs/specs

cat > expenses/__init__.py <<'EOF'
"""Household expenses: categories and amounts."""
EOF

cat > expenses/categories.py <<'EOF'
"""Totals per category."""


def by_category(expenses):
    """Total cents per category name, as each expense writes it."""
    totals = {}
    for item in expenses:
        totals[item["category"]] = totals.get(item["category"], 0) + item["cents"]
    return totals
EOF

cat > expenses/money.py <<'EOF'
"""Amounts as people read them."""


def format_cents(cents):
    """Cents as euros with two decimals: 123456 gives `1234.56`."""
    return f"{cents / 100:.2f}"
EOF

cat > tests/test_categories.py <<'EOF'
import unittest

from expenses.categories import by_category


class CategoriesTest(unittest.TestCase):
    def test_totals_per_category(self):
        items = [
            {"category": "food", "cents": 1250},
            {"category": "food", "cents": 750},
            {"category": "rent", "cents": 90000},
        ]
        self.assertEqual(by_category(items), {"food": 2000, "rent": 90000})


if __name__ == "__main__":
    unittest.main()
EOF

cat > tests/test_money.py <<'EOF'
import unittest

from expenses.money import format_cents


class MoneyTest(unittest.TestCase):
    def test_two_decimals(self):
        self.assertEqual(format_cents(123456), "1234.56")


if __name__ == "__main__":
    unittest.main()
EOF

cat > README.md <<'EOF'
# expenses

`expenses/categories.py` totals expenses per category; `expenses/money.py` writes amounts.
Run the tests with `python3 -B -m unittest discover -s tests`.
EOF

cat > docs/status.md <<'EOF'
# Status

Each change sets its own row when it lands.

| Item | State |
| --- | --- |
| Totals per category | done |
| Amounts with two decimals | done |
| Categories match whatever their case | planned |
| Amounts with a thousands separator | planned |
EOF

cat > docs/specs/next-changes.md <<'EOF'
# Next changes — design

Two changes for the next release. Neither depends on the other.

## Categories match whatever their case

`by_category` in `expenses/categories.py` totals `Food`, `food` and `FOOD` as one category,
keyed in lower case. `tests/test_categories.py` covers it. When it lands, its row of
`docs/status.md` reads `done`.

## Amounts with a thousands separator

`format_cents` in `expenses/money.py` writes a comma between each group of three digits:
`123456789` gives `1,234,567.89`. `tests/test_money.py` covers it. When it lands, its row of
`docs/status.md` reads `done`.

## Validation

`python3 -B -m unittest discover -s tests` passes, with a test for each change.
EOF

project=expenses
implementers="Two implementers work the tickets at the same time, each on its own branch."
# shellcheck source=../slicing/store.sh
. "$here/../slicing/store.sh"

cat > .outcomebound/ticket-claims.json <<'EOF'
{
 "version": 1,
 "cwd": "..",
 "claims": [
  {
   "name": "category-tests",
   "risk": "the totals per category are wrong",
   "kind": "test",
   "command": ["python3", "-B", "-m", "unittest", "tests.test_categories"],
   "required_paths": ["expenses/categories.py", "tests/test_categories.py"]
  },
  {
   "name": "money-tests",
   "risk": "an amount is written wrongly",
   "kind": "test",
   "command": ["python3", "-B", "-m", "unittest", "tests.test_money"],
   "required_paths": ["expenses/money.py", "tests/test_money.py"]
  }
 ]
}
EOF

cat > AGENTS.md <<'NOTE'
# expenses

`expenses/` totals household expenses and writes amounts. Run the tests with
`python3 -B -m unittest discover -s tests`. How tickets are drafted and how work lands is in
`CONTRIBUTING.md`; `docs/status.md` records the state of each change.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

# shellcheck source=../slicing/finish.sh
. "$here/../slicing/finish.sh"
git tag seed
echo "fixture ready: $target"
