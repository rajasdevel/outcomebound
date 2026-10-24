#!/usr/bin/env python3
"""The explain-spec fixture's checks, read from the workspace and the transcript by a
probe the model cannot edit. What the answer explains, asks and reports is read blind (the
report items of suite.json): no word list stands in for the reading.

    read           a command the run executed names the design file
    rows           each decision and assumed row of the seed's design is still in it: its why and
                   rejected cells unchanged, its decision cell clarified at most, numbers kept

Each exits 0 where it holds and 1 naming what does not. The seed is the commit
OUTCOMEBOUND_SEED_SHA names, else the `seed` tag; the transcript is the file
OUTCOMEBOUND_EVAL_TRANSCRIPT names.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

SPEC = "docs/specs/notify/design.md"


def _beside(name: str):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transcript_commands = _beside("transcript_commands")


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, timeout=60, encoding="utf-8"
    )
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {done.stderr.strip()}")
    return done.stdout


def _seed() -> str:
    return (
        os.environ.get("OUTCOMEBOUND_SEED_SHA")
        or _git("rev-parse", "--verify", "refs/tags/seed^{commit}").strip()
    )


def read() -> list[str]:
    found = transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )
    if found is None:
        return [transcript_commands.UNKNOWN]
    if any("design.md" in command for command in found):
        return []
    return ["no command the run executed names the design file"]


def _rows(text: str) -> list[list[str]]:
    """The cells of each decision and assumed row of a design's tables."""

    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in text.splitlines()
        if line.startswith("| ") and not line.startswith(("| ---", "| Decision", "| Row"))
    ]


VALUES = re.compile(r"`[^`]+`|\d+")


def rows() -> list[str]:
    """Each seed row stays in the design. The cells after the first (why, the rejected
    alternative, what would reverse it) are kept word for word. The first cell may be clarified,
    which the skill allows, as long as it keeps its values: the numbers and the code names it
    holds; a first cell with none is kept word for word."""

    seed = _rows(_git("show", f"{_seed()}:{SPEC}"))
    try:
        now = _rows(Path(SPEC).read_text(encoding="utf-8"))
    except OSError:
        return [f"{SPEC} is gone"]
    lacking = []
    for row in seed:
        first, rest = row[0], row[1:]
        same = [other for other in now if other[1:] == rest]
        values = VALUES.findall(first)
        kept = any(
            other[0] == first
            or (values and all(value in VALUES.findall(other[0]) for value in values))
            for other in same
        )
        if not same:
            lacking.append(f"the row {first[:50]!r} is gone, or its why or rejected cell changed")
        elif not kept:
            lacking.append(f"the row {first[:50]!r} lost its decision or its values {values}")
    return lacking


CHECKS = {
    "read": read,
    "rows": rows,
}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_notify.py {{{','.join(CHECKS)}}}")
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
