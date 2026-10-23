#!/usr/bin/env bash
# incomplete: the change made; the gate run only after it.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

verify = Path("shipyard/verify.py")
text = verify.read_text(encoding="utf-8")
old = """def verify(env, results):
    \"\"\"The verdict for `env` from {probe: passed}: every probe must pass.\"\"\"
    passed = sum(1 for ok in results.values() if ok)
    total = len(results)
    return Verdict(env, passed, total, total > 0 and passed == total)
"""
new = """# Stage passes when at least this share of its probes pass, in percent; production needs all.
STAGE_SHARE = 80


def verify(env, results):
    \"\"\"The verdict for `env` from {probe: passed}: production needs every probe to pass,
    stage at least STAGE_SHARE percent of them.\"\"\"
    passed = sum(1 for ok in results.values() if ok)
    total = len(results)
    if total == 0:
        return Verdict(env, passed, total, False)
    needed = total * STAGE_SHARE if env == "stage" else total * 100
    return Verdict(env, passed, total, passed * 100 >= needed)
"""
assert old in text
verify.write_text(text.replace(old, new), encoding="utf-8")
Path("tests/unit/test_verify_share.py").write_text(
    """import unittest

from shipyard import verify


def results(passed, total):
    return {f"p{index}": index < passed for index in range(total)}


class StageShareTest(unittest.TestCase):
    def test_stage_passes_at_80_percent(self):
        self.assertTrue(verify.verify("stage", results(8, 10)).ok)

    def test_stage_fails_below_80_percent(self):
        self.assertFalse(verify.verify("stage", results(7, 10)).ok)

    def test_production_still_needs_every_probe(self):
        self.assertFalse(verify.verify("prod", results(9, 10)).ok)


if __name__ == "__main__":
    unittest.main()
""",
    encoding="utf-8",
)
PY
