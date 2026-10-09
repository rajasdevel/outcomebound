"""Build a fixed codec with vacuous proposed regression tests."""

from __future__ import annotations

import sys
from pathlib import Path
from runpy import run_path

build = run_path(str(Path(__file__).resolve().parent.parent / "patch-validation/support.py"))[
    "build"
]

FIXED = """def encode(values):
    return ",".join(str(value) for value in values)

def decode(text):
    return [] if not text else [int(part) for part in text.split(",")]

def normalize(values):
    return sorted(set(values))
"""
LOSS = FIXED.replace("str(value)", "str(abs(value))")
ROTATION = FIXED.replace("return sorted(set(values))", "return sorted(set(values))[1:]")
COUPLED = FIXED.replace("for value in values", "for value in reversed(values)").replace(
    '[int(part) for part in text.split(",")]', '[int(part) for part in text.split(",")][::-1]'
)
PROPOSED = """import unittest
from codec import encode, normalize

class CodecTest(unittest.TestCase):
    def test_samples(self):
        for values in ():
            self.assertEqual(encode(values), encode(values))

    def test_normalization(self):
        self.assertEqual(normalize([]), normalize([]))
"""
CONTRACT = """# Integer codec

encode(values) returns decimal signed integers, separated by commas, in input order.
The empty list encodes as an empty string.
decode(text) returns those integers in the order in which they appear.
normalize(values) returns unique integers in ascending order.
These functions accept lists of integers, including negative values and duplicates.
The current implementation meets this contract. test_codec.py is the proposed test.
"""

if __name__ == "__main__":
    build(
        Path(sys.argv[1]).resolve(),
        {
            "codec.py": FIXED,
            "test_codec.py": PROPOSED,
            "README.md": CONTRACT,
            "AGENTS.md": """# Integer codec

README.md defines the public interface. Use unittest and no new dependencies.
Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
""",
        },
    )
