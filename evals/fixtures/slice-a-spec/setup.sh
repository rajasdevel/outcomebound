#!/usr/bin/env bash
# An expenses report with a short design for CSV output, a declared ticket store and claims
# plan, and the project's ticket template. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > report.py <<'EOF'
"""The monthly report: totals per month and category."""


def monthly_totals(expenses):
    """Total cents per (month, category), a month written YYYY-MM."""
    totals = {}
    for item in expenses:
        key = (item["date"][:7], item["category"])
        totals[key] = totals.get(key, 0) + item["cents"]
    return totals


def render_text(totals):
    """One line per month and category, sorted, amounts in euros."""
    return "\n".join(
        f"{month}  {category:<12} {cents / 100:>9.2f}"
        for (month, category), cents in sorted(totals.items())
    )
EOF

cat > expenses.py <<'EOF'
"""python3 expenses.py report: print the monthly report of expenses.json."""

import json
import sys

import report


def main(argv):
    if argv != ["report"]:
        print(__doc__, file=sys.stderr)
        return 2
    with open("expenses.json", encoding="utf-8") as handle:
        expenses = json.load(handle)
    print(report.render_text(report.monthly_totals(expenses)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
EOF

cat > test_report.py <<'EOF'
import unittest

from report import monthly_totals, render_text

EXPENSES = [
    {"date": "2026-08-03", "category": "food", "cents": 1250},
    {"date": "2026-08-19", "category": "food", "cents": 750},
    {"date": "2026-09-01", "category": "rent", "cents": 90000},
]


class ReportTest(unittest.TestCase):
    def test_totals_per_month_and_category(self):
        self.assertEqual(
            monthly_totals(EXPENSES), {("2026-08", "food"): 2000, ("2026-09", "rent"): 90000}
        )

    def test_text_is_one_line_per_total(self):
        self.assertEqual(len(render_text(monthly_totals(EXPENSES)).splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
EOF

cat > expenses.json <<'EOF'
[
 {"date": "2026-08-03", "category": "food", "cents": 1250},
 {"date": "2026-08-19", "category": "food", "cents": 750},
 {"date": "2026-09-01", "category": "rent", "cents": 90000}
]
EOF

cat > README.md <<'EOF'
# expenses

## Usage

`python3 expenses.py report` prints each month's total per category from `expenses.json`.
EOF

mkdir -p docs/specs
cat > docs/specs/csv-report.md <<'EOF'
# CSV report — design

## Outcome

`python3 expenses.py report --format csv` prints the monthly report as CSV, which the finance
sheet imports as it stands. `--format text`, the default, prints what `report` prints today.

## Decisions

- Columns, in this order: `month,category,total`. `month` is written `YYYY-MM` and `total` in
  whole cents. One header row, then one row per month and category, sorted by month and then
  by category.
- Rows are written by the standard library's `csv` module with `lineterminator="\n"`.
- Any other `--format` value exits 2, printing `unknown format: <value>` on standard error.

## Where it lands

`report.py` gains the CSV writer beside `render_text`; `expenses.py` parses `--format`;
`test_report.py` covers both formats; the usage section of `README.md` shows the option.

## Validation

`python3 -B -m unittest test_report` passes, with a test for each decision above.
EOF

cat > CONTRIBUTING.md <<'EOF'
# Contributing

## Tickets

Tickets live on the tracker; `.outcomebound/tickets.json` declares it. A ticket is drafted as a
file `docs/tickets/<name>.md`: the heading `# <title>`, then the body of
`.github/ISSUE_TEMPLATE/ticket.md`. In its block, `reads` names the design sections the ticket
answers to, as `<path>#<heading anchor>`; `bounds` the paths its work may write,
comma-separated; `human-only` is `no` unless a person must do the work; and each `done-when`
item names a claim of `.outcomebound/ticket-claims.json`. One implementer works the tickets, one
at a time.

## How work lands

Each ticket lands as one commit on `main`, its message ending with a `Ticket: #<number>` line.
EOF

mkdir -p .github/ISSUE_TEMPLATE .outcomebound
cat > .github/ISSUE_TEMPLATE/ticket.md <<'EOF'
## Outcome

## Design

## Tests

## Limits

<!-- outcomebound:begin id=ticket v=1 -->
reads:
bounds:
human-only: no
done-when:
<!-- outcomebound:end id=ticket -->
EOF

cat > .outcomebound/tickets.json <<'EOF'
{
 "version": 1,
 "store": "github",
 "repo": "example/expenses",
 "label": "ob-ticket",
 "human_label": "human-only",
 "request_label": "human-requested",
 "claims": ".outcomebound/ticket-claims.json",
 "default_branch": "main"
}
EOF

cat > .outcomebound/ticket-claims.json <<'EOF'
{
 "version": 1,
 "cwd": "..",
 "claims": [
  {
   "name": "report-tests",
   "risk": "the report prints wrong totals",
   "kind": "test",
   "command": ["python3", "-B", "-m", "unittest", "test_report"],
   "required_paths": ["report.py", "test_report.py"]
  }
 ]
}
EOF

cat > AGENTS.md <<'NOTE'
# expenses

`expenses.py report` prints the monthly report of `expenses.json`; `report.py` computes it.
Run the tests with `python3 -B -m unittest`. How tickets are drafted and how work lands is in
`CONTRIBUTING.md`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p checks
cp "$repo/evals/graders/drafts.py" checks/drafts.py
chmod +x checks/*

# The core skill, where the note names it and where codex looks for skills;
# none in the kernel-off arm.
bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
# The sample hooks Git installs are inert, and removing them lets the graders
# treat any entry under .git/hooks as what it is: something a run put there.
rm -f .git/hooks/*.sample
# Bytecode and check logs are byproducts of running a check, not edits.
printf '__pycache__/\n.outcomebound-checks/\n' >> .git/info/exclude
git add -A
git commit -qm "seed"
git tag seed
echo "fixture ready: $target"
