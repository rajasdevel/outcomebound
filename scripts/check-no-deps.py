#!/usr/bin/env python3
"""Guard: the engine and this repository's scripts must import stdlib only.

Run as part of `make gate`. Exits 0 when clean, 1 on any non-stdlib import.
Mirrors tests/test_no_third_party_imports.py so the same invariant is enforced
both in the test suite and as a standalone gate step.
"""

import argparse
import ast
import glob
import os
import sys

STDLIB = set(sys.stdlib_module_names)
ROOTED_PATTERNS = ("outcomebound_tools/**/*.py", "scripts/**/*.py")
ALLOWED_FIRST_PARTY = {"outcomebound_tools"}


def _module_names(node):
    """Every alias in one import statement, not just the first.

    `import os, requests` declares two modules, and each is held to the standard
    library: reading only the first alias would let the second through.
    """
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        return [(node.module or "").split(".")[0]]
    return []


def violations(root="."):
    out: list[tuple[str, str]] = []
    for pattern in ROOTED_PATTERNS:
        for path in sorted(glob.glob(os.path.join(root, pattern), recursive=True)):
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                out.extend(
                    (path, module)
                    for module in _module_names(node)
                    if module and module not in STDLIB and module not in ALLOWED_FIRST_PARTY
                )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check that the engine and its scripts import the standard library only."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="the repository root to check (default: the current directory)",
    )
    root = parser.parse_args(argv).root
    bad = violations(root)
    if bad:
        for path, module in bad:
            print(f"FAIL: {path} imports non-stdlib '{module}'")
        return 1
    print(f"OK: {', '.join(ROOTED_PATTERNS)} import stdlib only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
