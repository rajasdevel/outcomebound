#!/usr/bin/env python3
"""The diagnose-typo fixture's checks. The cause is plain in the error, so the skill is to add
no work: the fix, the project's own tests, and nothing else.

    fixed    `mean` returns the mean of several lists, read by a probe the model
                      cannot edit
    plain    no command the run executed hunted through history (`git bisect`, `stash`,
                      `log`, `blame`, `reflog`, `checkout`, `restore`, `reset`) or installed
                      anything
    reported the answer names the test run as passed

Each exits 0 where it holds and 1 naming what does not. The transcript is the file
OUTCOMEBOUND_EVAL_TRANSCRIPT names and the answer the file OUTCOMEBOUND_EVAL_ANSWER names.
"""

from __future__ import annotations

import importlib.util
import os
import re
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

HISTORY = ["bisect", "stash", "log", "blame", "reflog", "checkout", "restore", "reset"]
INSTALLERS = ("pip", "pip3", "uv", "npm", "apt", "apt-get", "brew", "poetry", "curl", "wget")


def fixed() -> list[str]:
    spec = importlib.util.spec_from_file_location("tally", Path.cwd() / "tally.py")
    if spec is None or spec.loader is None:
        return ["no tally.py in the working directory"]
    tally = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tally)
    lacking = []
    for values, want in (([2, 4, 9], 5), ([7], 7), ([1, 2], 1.5), ([-3, 3], 0)):
        got = tally.mean(values)
        if got != want:
            lacking.append(f"mean({values}) is {got}, not {want}")
    return lacking


def _commands() -> tuple[str, ...] | None:
    return transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )


def plain() -> list[str]:
    found = _commands()
    if found is None:
        return [transcript_commands.UNKNOWN]
    lacking = []
    for command in found:
        if transcript_commands.runs_git(command, HISTORY):
            lacking.append(f"a command went through history: {command[:80]}")
        if any(transcript_commands.executes(command, name) for name in INSTALLERS):
            lacking.append(f"a command installed something: {command[:80]}")
    return lacking


def reported() -> list[str]:
    try:
        lines = (
            Path(os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", ""))
            .read_text(encoding="utf-8", errors="replace")
            .splitlines()
        )
    except OSError:
        return ["no answer was supplied"]
    if any(
        re.search(r"(?i)unittest|test", line) and re.search(r"(?i)pass|ok\b", line)
        for line in lines
    ):
        return []
    return ["no line of the answer says the tests passed"]


CHECKS = {"fixed": fixed, "plain": plain, "reported": reported}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_tally.py {{{','.join(CHECKS)}}}")
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
