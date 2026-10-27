from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any

"""Run only added unittest methods, with a control or a behaviour mutation before imports."""


root, mode, originals = sys.argv[1:]
sys.path.insert(0, root)
parser: Any = importlib.import_module("textparse")
actual = parser.parse_pairs


def control(text):
    return actual(text)


def truncate(text):
    return {key: value.split("=")[0] for key, value in actual(text).items()}


parser.parse_pairs = control if mode == "control" else truncate
old = json.loads(originals)
spec = importlib.util.spec_from_file_location(
    "parser_oracles", Path(__file__).with_name("parser_oracles.py")
)
if spec is None or spec.loader is None:
    raise SystemExit("no sealed parser_oracles.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


added = []
for test in flatten(
    unittest.defaultTestLoader.discover(str(Path(root) / "tests"), top_level_dir=root)
):
    module = sys.modules[type(test).__module__]
    if module.__file__ is None:
        raise SystemExit("the test module has no source path")
    filename = str(Path(module.__file__).relative_to(root)).replace("\\", "/")
    name = test._testMethodName
    if (type(test).__qualname__, name) not in helper.methods(old.get(filename, "")):
        added.append(test)
result = unittest.TextTestRunner().run(unittest.TestSuite(added))
if not added or result.errors or result.skipped:
    raise SystemExit("no added tests, or an import/setup error or skip; not regression evidence")
if mode == "control" and not result.wasSuccessful():
    raise SystemExit("the added tests fail the control")
if mode == "truncate" and not result.failures:
    raise SystemExit("truncating equals in the value caused no assertion failure")
