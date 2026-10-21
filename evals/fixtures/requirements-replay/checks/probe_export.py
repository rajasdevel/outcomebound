#!/usr/bin/env python3
"""The requirements-replay fixture's check, read from the workspace by a probe the model cannot
edit.

    behaviour   `to_csv` writes ISO dates, keeps the amounts in cents (the issue's correction),
                keeps the column order and leaves out a cancelled order, whatever the data

What the report tells the person (the four requirements, the correction, where each came from)
is not checked here: `suite.json` lists it as report items, which a person reads blind. Exits 0
where it holds and 1 naming what does not.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import ModuleType

ORDERS = [
    {"id": 7, "placed": "04/03/2026", "customer": "Ada", "cents": 1250, "status": "shipped"},
    {"id": 8, "placed": "05/03/2026", "customer": "Bo", "cents": 990, "status": "cancelled"},
    {"id": 9, "placed": "31/12/2025", "customer": "Cy", "cents": 40000, "status": "paid"},
]
WANTED = "7,2026-03-04,Ada,1250,shipped\n9,2025-12-31,Cy,40000,paid\n"


def behaviour() -> list[str]:
    module = ModuleType("export")
    module.__dict__.update(runpy.run_path(str(Path.cwd() / "export.py"), run_name="export"))
    got = module.to_csv([dict(order) for order in ORDERS])
    if got == WANTED:
        return []
    lacking = [f"to_csv gives {got!r}, not {WANTED!r}"]
    if any(line.startswith("8,") for line in got.splitlines()):
        lacking.append("a cancelled order is in the output")
    if "04/03/2026" in got or "31/12/2025" in got:
        lacking.append("a date is not written as an ISO date")
    if "12.50" in got or "400.00" in got:
        lacking.append("an amount is in euros, not in cents")
    return lacking


CHECKS = {"behaviour": behaviour}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_export.py {{{','.join(CHECKS)}}}")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
