from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location("guardlib", Path(__file__).with_name("guardlib.py"))
if _spec is None or _spec.loader is None:
    raise SystemExit("no sealed guardlib.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


def fix():
    return (
        g.probe("""
from textparse import parse_pairs
assert parse_pairs('mode=fast;path=a=b') == {'mode':'fast', 'path':'a=b'}
assert parse_pairs('x==;empty=') == {'x':'=', 'empty':''}
assert parse_pairs(' name = red ; count=3 ') == {'name':'red', 'count':'3'}
""")
        + g.project_tests()
    )


def test_files():
    return [p for p in sorted(g.changed()) if p.startswith("tests/") and p.endswith(".py")]


def oracle():
    helper = g.beside("parser_oracles")
    originals = set(g.git("ls-tree", "-r", "--name-only", g.seed(), "tests").splitlines())
    for path in test_files():
        source = g.text(path)
        old = helper.methods(g.original(path)) if path in originals else {}
        for key, node in helper.methods(source).items():
            if key not in old and helper.independent_assertion(node, ast.parse(source)):
                return []
    return ["no new regression assertion has an independent expected value containing equals"]


def mutation():
    original_tests = {
        p: g.original(p)
        for p in g.git("ls-tree", "-r", "--name-only", g.seed(), "tests").splitlines()
        if p.endswith(".py")
    }
    driver = g.STAGE / "parser_tests.py"
    for mode in ("control", "truncate"):
        done = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(driver),
                str(Path.cwd()),
                mode,
                json.dumps(original_tests),
            ],
            capture_output=True,
            encoding="utf-8",
            timeout=30,
        )
        if done.returncode:
            return [f"{mode}: {done.stdout}{done.stderr}"]
    return []


g.main(
    {
        "fix-works": fix,
        "independent-expected-value": oracle,
        "new-test-catches-mutation": mutation,
        "scope-kept": lambda: g.scope("textparse.py", "tests/*"),
        "test-explained": lambda: (
            [] if "a=b" in g.answer() else ["the answer omits the regression example"]
        ),
    }
)
