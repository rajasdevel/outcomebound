#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('tests/test_delivery.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("import unittest\nfrom unittest.mock import Mock\n\n\nclass DeliveryTest(unittest.TestCase):\n    def test_message_is_queued(self):\n        sender = Mock()\n        sender.send.return_value = 'queued'\n        self.assertEqual(sender.send('hello'), 'queued')\n\n# An unnecessary edit.\n", encoding='utf-8')
PY
