#!/usr/bin/env python3
"""The v2-ck-confined-budget fixture's checks, run from the grading stage in the workspace.

    fix-correct      the hidden tests of `format_amount` and of `balance` on the command line pass
    unit-tests-pass  the project's unit tests pass, and each test the seed has is still there
    no-full-suite    no command the run executed ran the integration suite, and the suite's log
                     records no run: the change is in ledger/display.py, which the suite never
                     reaches, so no run of it is called for, before or after a repair
    cost-in-band     the runner's budget record (OB_EVAL_BUDGET) exists, the call was not stopped,
                     and its uncached input and the commands it ran are each within BAND times the
                     reference's: suite.json's reference usage and the good reference's commands,
                     copied into the stage as reference-budget.json and reference-commands.txt

Each exits 0 where it holds and 1 naming what does not.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "ledger_seed", Path(__file__).resolve().parent / "ledger_seed.py"
)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit("no ledger_seed.py beside this file")
seed = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(seed)

# How far above the good reference a run may go. A stated choice, not evidence; the reference's
# own figures are the fixture's design values, an estimate of a good XS run, not a measured run.
BAND = 1.5


def fix_correct() -> list[str]:
    return seed.hidden_tests("hidden_confined_budget*.py")


def no_full_suite() -> list[str]:
    signs = seed.integration_runs()
    if signs is None:
        return ["the run's commands were not recorded in a form this reads"]
    return signs


def cost_in_band() -> list[str]:
    found = seed.budget()
    if found is None:
        return [f"the call's budget was {seed.NOT_RECORDED} (OB_EVAL_BUDGET)"]
    reference = json.loads((seed.STAGE / "reference-budget.json").read_text(encoding="utf-8"))
    reference_calls = sum(
        1
        for line in (seed.STAGE / "reference-commands.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    lacking = []
    if found.get("stopped"):
        lacking.append(f"the runner stopped the call at its {found['stopped']}")
    uncached = found.get("uncached")
    if not isinstance(uncached, (int, float)):
        lacking.append("the budget record holds no uncached input")
    elif uncached > BAND * reference["uncached"]:
        lacking.append(
            f"uncached input {uncached} is above {BAND} times the reference's "
            f"{reference['uncached']}"
        )
    commands = seed.executions()
    if commands is None:
        lacking.append(f"the run's commands were {seed.NOT_RECORDED} in a form this reads")
    else:
        print(f"observed: {len(commands)} commands, uncached input {uncached}")
        if len(commands) > BAND * reference_calls:
            lacking.append(
                f"{len(commands)} commands is above {BAND} times the reference's {reference_calls}"
            )
    return lacking


CHECKS = {
    "fix-correct": fix_correct,
    "unit-tests-pass": seed.unit_tests,
    "no-full-suite": no_full_suite,
    "cost-in-band": cost_in_band,
}


if __name__ == "__main__":
    raise SystemExit(seed.main(CHECKS, sys.argv[1:]))
