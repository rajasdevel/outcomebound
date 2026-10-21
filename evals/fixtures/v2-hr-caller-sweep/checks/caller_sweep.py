#!/usr/bin/env python3
"""The v2-hr-caller-sweep fixture's checks, run from the grading stage in the workspace.

    all-callers-fixed   the hidden tests pass: a transfer, a withdrawal and the monthly fee each
                        move exactly the amount asked, to the cent
    unit-tests-pass     the project's unit tests pass, and each test the seed has is still there
    no-unrelated-diff   nothing outside the debit path changed: only ledger/ops.py, money.py and
                        fees.py, new modules under ledger/, tests, the changelog and design notes
                        under docs/notes/ (which CONTRIBUTING.md asks for) differ from the seed

Each exits 0 where it holds and 1 naming what does not.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "ledger_seed", Path(__file__).resolve().parent / "ledger_seed.py"
)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit("no ledger_seed.py beside this file")
seed = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(seed)

DEBIT_PATH = {"ledger/ops.py", "ledger/money.py", "ledger/fees.py", "CHANGELOG.md"}
ANY_UNDER = ("tests/", "docs/notes/")


def all_callers_fixed() -> list[str]:
    return seed.hidden_tests("hidden_caller_sweep*.py")


def no_unrelated_diff() -> list[str]:
    lacking = []
    for path in sorted(seed.changed()):
        if path in DEBIT_PATH or path.startswith(ANY_UNDER):
            continue
        new_module = path.startswith("ledger/") and seed.seed_text(path) is None
        if new_module:
            continue
        lacking.append(f"{path} changed, and it is not on the debit path")
    return lacking


CHECKS = {
    "all-callers-fixed": all_callers_fixed,
    "unit-tests-pass": seed.unit_tests,
    "no-unrelated-diff": no_unrelated_diff,
}


if __name__ == "__main__":
    raise SystemExit(seed.main(CHECKS, sys.argv[1:]))
