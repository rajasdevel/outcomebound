#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -I -B - <<'PARTIAL'
from pathlib import Path
path=Path("tally/window.py")
path.write_text(path.read_text().replace("entry.day <= until", "entry.day < until"))
Path("tests/test_window.py").write_text("import unittest\nfrom datetime import date\nfrom tally.model import Entry\nfrom tally.window import select\n\nclass WindowTest(unittest.TestCase):\n    def test_open_lower_bound(self):\n        rows=[Entry(date(2026,2,n),'work','member',n) for n in (1,2,3)]\n        self.assertEqual(select(iter(rows),since=date(2026,2,2)),[rows[1],rows[2]])\n")
PARTIAL
python3 -B -m unittest tests.test_window

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
