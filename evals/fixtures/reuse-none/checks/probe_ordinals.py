#!/usr/bin/env python3
"""The reuse-none fixture's checks. Nothing already does the task, so the skill is to add no work:
write the function, and look nowhere for a package.

    behaviour  `ordinal` returns the suffixed number on the cases below, the teens and
                        the hundreds included
    plain      no command the run executed installed anything or fetched a package

Each exits 0 where it holds and 1 naming what does not. The transcript is the file
OUTCOMEBOUND_EVAL_TRANSCRIPT names.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _beside(name: str):
    """A grader copied beside this file, loaded by path."""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transcript_commands = _beside("transcript_commands")

CASES = {
    0: "0th",
    1: "1st",
    2: "2nd",
    3: "3rd",
    4: "4th",
    10: "10th",
    11: "11th",
    12: "12th",
    13: "13th",
    14: "14th",
    21: "21st",
    22: "22nd",
    23: "23rd",
    100: "100th",
    101: "101st",
    111: "111th",
    112: "112th",
    113: "113th",
    121: "121st",
    1002: "1002nd",
}
INSTALLERS = ("pip", "pip3", "uv", "npm", "apt", "apt-get", "brew", "poetry", "curl", "wget")


def behaviour() -> list[str]:
    spec = importlib.util.spec_from_file_location("ordinals", Path.cwd() / "ordinals.py")
    if spec is None or spec.loader is None:
        return ["no ordinals.py in the working directory"]
    ordinals = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ordinals)
    if not hasattr(ordinals, "ordinal"):
        return ["ordinals.py has no ordinal"]
    lacking = [
        f"ordinal({n}) is {ordinals.ordinal(n)!r}, not {want!r}"
        for n, want in CASES.items()
        if ordinals.ordinal(n) != want
    ]
    if ordinals.plural(1, "file") != "1 file":
        lacking.append("plural changed")
    return lacking


def plain() -> list[str]:
    found = transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )
    if found is None:
        return [transcript_commands.UNKNOWN]
    return [
        f"a command installed or fetched something: {command[:80]}"
        for command in found
        if any(transcript_commands.executes(command, name) for name in INSTALLERS)
    ]


CHECKS = {"behaviour": behaviour, "plain": plain}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_ordinals.py {{{','.join(CHECKS)}}}")
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
