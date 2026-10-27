#!/usr/bin/env bash
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('textparse.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('def parse_pairs(text):\n    """Read semicolon-separated key=value pairs. A value can contain equals signs."""\n    result = {}\n    for field in text.split(\';\'):\n        key, value = field.split(\'=\', 1)\n        result[key.strip()] = value.strip()\n    return result\n', encoding='utf-8')
PY
python3 -I -B - <<'PY'
from pathlib import Path
p = Path('tests/test_equals.py')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text("import unittest\nfrom textparse import parse_pairs\n\n\nclass EqualsValueTest(unittest.TestCase):\n    def test_equals_in_value(self):\n        expected = {'mode': 'fast', 'path': 'a' + '=' + 'b'}\n        self.assertEqual(parse_pairs('mode=fast;path=a=b'), expected)\n", encoding='utf-8')
PY
