#!/usr/bin/env bash
# A small ledger package with a docstring check people run by hand, which today reports
# findings in `src/`, a short design that makes that check a gate with no baseline, a declared
# ticket store and claims plan, and the project's ticket template. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

mkdir -p src/ledger tests tools .github/workflows docs/specs

cat > src/ledger/__init__.py <<'EOF'
"""A household ledger: entries read from text lines, and their totals."""
EOF

cat > src/ledger/entries.py <<'EOF'
"""Ledger entries, one a line: `YYYY-MM-DD account cents`."""


def parse_line(line):
    date, account, cents = line.split()
    return {"date": date, "account": account, "cents": int(cents)}


def is_valid(entry):
    """Whether an entry has a ten-character date and a non-empty account."""
    return len(entry["date"]) == 10 and bool(entry["account"])
EOF

cat > src/ledger/totals.py <<'EOF'
"""Totals over ledger entries."""


def total(entries):
    return sum(entry["cents"] for entry in entries)


def by_account(entries):
    sums = {}
    for entry in entries:
        sums[entry["account"]] = sums.get(entry["account"], 0) + entry["cents"]
    return sums
EOF

cat > tests/test_ledger.py <<'EOF'
import unittest

from ledger.entries import is_valid, parse_line
from ledger.totals import by_account, total

LINES = ["2026-08-03 food 1250", "2026-08-19 food 750", "2026-09-01 rent 90000"]


class LedgerTest(unittest.TestCase):
    def test_a_line_reads_as_an_entry(self):
        entry = parse_line(LINES[0])
        self.assertEqual(entry, {"date": "2026-08-03", "account": "food", "cents": 1250})
        self.assertTrue(is_valid(entry))

    def test_totals(self):
        entries = [parse_line(line) for line in LINES]
        self.assertEqual(total(entries), 92000)
        self.assertEqual(by_account(entries), {"food": 2000, "rent": 90000})


if __name__ == "__main__":
    unittest.main()
EOF

cat > tools/doclint.py <<'EOF'
"""python3 tools/doclint.py PATH...: list each public function without a docstring.

Prints one `path:line: name` a finding and exits 1 where there is any, else exits 0.
"""

import ast
import sys
from pathlib import Path


def findings(paths):
    found = []
    for root in paths:
        for path in sorted(Path(root).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    if ast.get_docstring(node) is None:
                        found.append(f"{path.as_posix()}:{node.lineno}: {node.name}")
    return found


if __name__ == "__main__":
    lines = findings(sys.argv[1:] or ["src"])
    print("\n".join(lines))
    sys.exit(1 if lines else 0)
EOF

cat > Makefile <<'EOF'
.PHONY: test check

test:
	PYTHONPATH=src python3 -B -m unittest discover -s tests

check: test
EOF

cat > .github/workflows/ci.yml <<'EOF'
name: ci
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make test
EOF

cat > README.md <<'EOF'
# ledger

A household ledger: `src/ledger/entries.py` reads entries, `src/ledger/totals.py` sums them.

## Development

`make test` runs the tests. `python3 tools/doclint.py src` lists each public function without
a docstring; it is run by hand today.
EOF

cat > docs/specs/doc-gate.md <<'EOF'
# Docstring gate — design

## Outcome

Every change runs the docstring check: `make check` runs `python3 tools/doclint.py src` after
the tests and fails on any finding, and the CI workflow runs `make check` on each pull request.

## Decisions

- The gate has no baseline: any finding fails it.
- The check reads all of `src`; `tests` and `tools` are not checked.
- CI runs `make check` in place of `make test`.

## Where it lands

`Makefile` gains the docstring step in its `check` target; `.github/workflows/ci.yml` runs
`make check`.

## Validation

The `check` claim of `.outcomebound/ticket-claims.json` passes.
EOF

project=ledger
implementers="One implementer works the tickets, one at a time."
# shellcheck source=../slicing/store.sh
. "$here/../slicing/store.sh"

cat > .outcomebound/ticket-claims.json <<'EOF'
{
 "version": 1,
 "cwd": "..",
 "claims": [
  {
   "name": "tests",
   "risk": "the ledger reads or sums entries wrongly",
   "kind": "test",
   "command": ["make", "test"],
   "required_paths": ["Makefile", "tests/test_ledger.py"]
  },
  {
   "name": "check",
   "risk": "a change lands that the project's own check refuses",
   "kind": "static",
   "command": ["make", "check"],
   "required_paths": ["Makefile"]
  }
 ]
}
EOF

cat > AGENTS.md <<'NOTE'
# ledger

`src/ledger` reads ledger entries and sums them. Run the tests with `make test`. How tickets
are drafted and how work lands is in `CONTRIBUTING.md`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

# shellcheck source=../slicing/finish.sh
. "$here/../slicing/finish.sh"
git tag seed
echo "fixture ready: $target"
