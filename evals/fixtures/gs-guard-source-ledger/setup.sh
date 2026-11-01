#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
. "$here/../seeds/guards/base.sh"
mkdir -p '.'
cat > 'AGENTS.md' <<'SEED'
# Project report

Python standard library only. `make test` runs the focused tests. requirements.txt is the current brief.
SEED
mkdir -p '.'
cat > 'README.md' <<'SEED'
# Project report

report.render(rows) returns CSV. Rows have name, status, owner and archived. dispositions.md records each source item as implemented, deferred or rejected, with source text and evidence. The earlier brief and dispositions are in Git history.
SEED
mkdir -p '.'
cat > 'requirements.txt' <<'SEED'
R1 | Write CSV with a header and one row per active project.
R2 | Keep the input order.
R3 | Leave archived projects out of the report.
SEED
mkdir -p '.'
cat > 'dispositions.md' <<'SEED'
# Source dispositions

| Item | Source text | Disposition | Evidence |
| --- | --- | --- | --- |
| R1 | Write CSV with a header and one row per active project. | implemented | report.py |
| R2 | Keep the input order. | implemented | report.py |
| R3 | Leave archived projects out of the report. | implemented | report.py |
SEED
mkdir -p '.'
cat > 'report.py' <<'SEED'
import csv
import io


def render(rows):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(['name', 'status'])
    for row in rows:
        if not row['archived']:
            writer.writerow([row['name'], row['status']])
    return out.getvalue()
SEED
mkdir -p 'tests'
cat > 'tests/test_report.py' <<'SEED'
import unittest
from report import render


class ReportTest(unittest.TestCase):
    def test_csv(self):
        text = render([dict(name='Aster', status='Open', owner='Team A', archived=False)])
        self.assertIn('Aster,Open', text)
SEED
field_close

git add -A
git commit -qm "report: implement the first brief and record its dispositions"
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('requirements.txt')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('R1 | Write CSV with a header and one row per active project.\nR2 | Sort projects by name without regard to case.\nR3 | Leave archived projects out of the report.\nR4 | Add owner after name and status in the CSV.\n', encoding='utf-8')
PY

guard_seed
