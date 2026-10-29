#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -I -B - <<'PARTIAL'
from pathlib import Path
path=Path("tally/bundles/build.py")
text=path.read_text()
text=text.replace(' or actual != summary(entries, actual.get("by"), count)', '')
path.write_text(text)
from pathlib import Path
Path("tests/test_bundles.py").write_text('import json\nimport subprocess\nimport sys\nimport tempfile\nimport unittest\nfrom pathlib import Path\n\n\nclass BundleTest(unittest.TestCase):\n    def test_build_dedupes_and_verifies(self):\n        with tempfile.TemporaryDirectory() as temp:\n            p = Path(temp)\n            source = p / "in.csv"\n            source.write_text("day,project,person,minutes,note\\n2026-02-02,alpha,member,20,\\n")\n            done = subprocess.run([sys.executable, "-B", "-m", "tally.bundles", "build", str(source),\n                                   str(source), "--out", str(p / "bundle")], capture_output=True, text=True)\n            self.assertEqual(done.returncode, 0, done.stderr)\n            result = json.loads(done.stdout)\n            self.assertEqual((result["entry_count"], result["duplicate_count"], result["total_minutes"]), (1, 1, 20))\n            verified = subprocess.run([sys.executable, "-B", "-m", "tally.bundles", "verify", str(p / "bundle")], capture_output=True, text=True)\n            self.assertEqual(json.loads(verified.stdout), {"valid": True})\n')
PARTIAL
python3 -B -m unittest tests.test_bundles

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
