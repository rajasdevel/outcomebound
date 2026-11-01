#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -I -B - <<'PARTIAL'
from pathlib import Path
path=Path("datapipe/reconcile/plan.py")
text=path.read_text().replace('if identity in history:', 'if identity in history and items.get(key, {}).get("version") == version:')
path.write_text(text)
from pathlib import Path
Path("tests/test_reconcile.py").write_text('import json\nimport subprocess\nimport sys\nimport tempfile\nimport unittest\nfrom pathlib import Path\n\n\nclass ReconcileTest(unittest.TestCase):\n    def test_plan_apply_and_restart(self):\n        with tempfile.TemporaryDirectory() as temp:\n            root=Path(temp); source=root/\'events.jsonl\'; db=root/\'state.sqlite\'\n            source.write_text(\'{"key":"a","version":1,"value":7}\\n\')\n            def invoke(command):\n                done=subprocess.run([sys.executable,\'-B\',\'-m\',\'datapipe.reconcile\',command,str(source),\'--db\',str(db)],capture_output=True,text=True)\n                self.assertEqual(done.returncode,0,done.stderr)\n                return json.loads(done.stdout)\n            self.assertEqual(invoke(\'plan\'),{\'actions\':[{\'key\':\'a\',\'version\':1,\'action\':\'insert\'}],\'active_count\':1,\'total_value\':7})\n            self.assertFalse(db.exists())\n            self.assertEqual(invoke(\'apply\')[\'total_value\'],7)\n            self.assertEqual(invoke(\'apply\')[\'actions\'],[{\'key\':\'a\',\'version\':1,\'action\':\'duplicate\'}])\n')
PARTIAL
python3 -B -m unittest tests.test_reconcile

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
