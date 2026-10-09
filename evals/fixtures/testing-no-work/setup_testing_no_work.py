"""An ordinary small repair already covered by an exact regression."""

from __future__ import annotations

import sys
from pathlib import Path
from runpy import run_path

build = run_path(str(Path(__file__).resolve().parent.parent / "patch-validation/support.py"))[
    "build"
]

BUG = """def item_label(count):
    return f"{count} item" if count <= 1 else f"{count} items"
"""
FIXED = BUG.replace("count <= 1", "count == 1")
TEST = """import unittest
from labels import item_label

class LabelTest(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(item_label(0), "0 items")

    def test_one(self):
        self.assertEqual(item_label(1), "1 item")

    def test_two(self):
        self.assertEqual(item_label(2), "2 items")
"""

if __name__ == "__main__":
    build(
        Path(sys.argv[1]).resolve(),
        {
            "labels.py": BUG,
            "test_labels.py": TEST,
            "README.md": """# Item label

item_label accepts a nonnegative integer. Only 1 uses the singular word item.
The reported defect is that 0 returns "0 item". The existing test covers this case.
""",
            "AGENTS.md": """# Item label

Run python3 -B -m unittest. Keep the existing tests unchanged.
Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
""",
        },
    )
