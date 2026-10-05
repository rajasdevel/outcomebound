#!/usr/bin/env bash
# A report tool whose output formats are modules of `formats/`, with a module registry that a
# test holds equal to those modules, a history whose last change added a format, a short design
# for one more format, a declared ticket store and claims plan, and the project's ticket
# template. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

mkdir -p formats audit tests docs/specs

cat > formats/__init__.py <<'EOF'
"""Output formats: each module `formats/<name>_out.py` has `render(rows)`."""
EOF

cat > formats/csv_out.py <<'EOF'
"""Rows as CSV, a header first."""

import csv
import io


def render(rows):
    """`rows` is a list of (name, cents) pairs."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["name", "cents"])
    writer.writerows(rows)
    return out.getvalue()
EOF

cat > report.py <<'EOF'
"""python3 report.py --format NAME: print the sample rows in the format `formats/NAME_out.py`."""

import importlib
import sys

ROWS = [("food", 2000), ("rent", 90000)]


def main(argv):
    if len(argv) != 2 or argv[0] != "--format":
        print(__doc__, file=sys.stderr)
        return 2
    try:
        module = importlib.import_module(f"formats.{argv[1]}_out")
    except ModuleNotFoundError:
        print(f"unknown format: {argv[1]}", file=sys.stderr)
        return 2
    sys.stdout.write(module.render(ROWS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
EOF

cat > audit/module_registry.py <<'EOF'
"""Every module of `formats/`, reviewed and named here; tests/test_module_registry.py holds the
two equal, so a module no one entered fails the suite."""

MODULES = ("formats.csv_out",)
EOF

cat > tests/test_module_registry.py <<'EOF'
import unittest
from pathlib import Path

from audit.module_registry import MODULES

ROOT = Path(__file__).resolve().parent.parent


class RegistryTest(unittest.TestCase):
    def test_every_format_module_is_entered(self):
        found = {
            f"formats.{path.stem}"
            for path in (ROOT / "formats").glob("*.py")
            if path.name != "__init__.py"
        }
        self.assertEqual(found, set(MODULES))


if __name__ == "__main__":
    unittest.main()
EOF

cat > tests/test_csv_out.py <<'EOF'
import unittest

from formats.csv_out import render


class CsvTest(unittest.TestCase):
    def test_header_then_rows(self):
        self.assertEqual(render([("food", 2000)]), "name,cents\nfood,2000\n")


if __name__ == "__main__":
    unittest.main()
EOF

cat > README.md <<'EOF'
# report

`python3 report.py --format csv` prints the sample rows as CSV. Each format is a module
`formats/<name>_out.py`. Run the tests with `python3 -B -m unittest discover -s tests`.
EOF

project=report
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
   "risk": "a format prints the rows wrongly",
   "kind": "test",
   "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests"],
   "required_paths": ["tests"]
  }
 ]
}
EOF

cat > AGENTS.md <<'NOTE'
# report

`report.py` prints the sample rows in one of the formats of `formats/`. Run the tests with
`python3 -B -m unittest discover -s tests`. How tickets are drafted and how work lands is in
`CONTRIBUTING.md`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

first_commit="Start the report tool with the CSV format"
# shellcheck source=../slicing/finish.sh
. "$here/../slicing/finish.sh"

# The last change before the design: a format added, with the registry entry it forced.
cat > formats/json_out.py <<'EOF'
"""Rows as a JSON list of objects."""

import json


def render(rows):
    """`rows` is a list of (name, cents) pairs."""
    return json.dumps([{"name": name, "cents": cents} for name, cents in rows]) + "\n"
EOF
cat > tests/test_json_out.py <<'EOF'
import unittest

from formats.json_out import render


class JsonTest(unittest.TestCase):
    def test_a_list_of_objects(self):
        self.assertEqual(render([("food", 2000)]), '[{"name": "food", "cents": 2000}]\n')


if __name__ == "__main__":
    unittest.main()
EOF
sed -i.bak 's/MODULES = ("formats.csv_out",)/MODULES = ("formats.csv_out", "formats.json_out")/' \
  audit/module_registry.py && rm audit/module_registry.py.bak
sed -i.bak 's/prints the sample rows as CSV/prints the sample rows as CSV, `--format json` as JSON/' \
  README.md && rm README.md.bak
git add -A
git commit -qm "Add the JSON format"

cat > docs/specs/markdown-format.md <<'EOF'
# Markdown format — design

## Outcome

`python3 report.py --format markdown` prints the rows as a Markdown table, which the monthly
note pastes as it stands.

## Decisions

- A header row `| name | cents |`, the separator row `| --- | --- |`, then one row per pair in
  the order given, each line ending in `\n`.
- `cents` is written as the integer it is.

## Where it lands

A new module `formats/markdown_out.py` with `render(rows)`, beside the other formats, which
`report.py` finds by name; `tests/test_markdown_out.py` covers it.

## Validation

`python3 -B -m unittest discover -s tests` passes, with a test for each decision above.
EOF
git add -A
git commit -qm "Design the Markdown format"
git tag seed
echo "fixture ready: $target"
