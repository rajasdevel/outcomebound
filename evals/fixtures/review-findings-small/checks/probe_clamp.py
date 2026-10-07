#!/usr/bin/env python3
"""The review-findings-small fixture's checks. The one finding is right and small, so the skill is
to add no work beyond the fix and the disposition.

    fixed        `clamp`'s behaviour is unchanged and its docstring no longer says the
                          bounds are excluded
    disposition  R1 has a `Disposition: fixed — <where>` line under its heading, and
                          the file still states what it reviewed
    plain        no command the run executed installed anything

Each exits 0 where it holds and 1 naming what does not. The transcript is the file
OUTCOMEBOUND_EVAL_TRANSCRIPT names.
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

HEADING = re.compile(r"^### ([A-Za-z0-9-]+) · (.+)$")
DISPOSITION = re.compile(r"^Disposition: fixed (?:—|--) (\S.*)$")
INSTALLERS = ("pip", "pip3", "uv", "npm", "apt", "apt-get", "brew", "poetry", "curl", "wget")


def fixed() -> list[str]:
    spec = importlib.util.spec_from_file_location("clamp", Path.cwd() / "clamp.py")
    if spec is None or spec.loader is None:
        return ["no clamp.py in the working directory"]
    clamp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(clamp)
    lacking = [
        f"clamp{args} is {clamp.clamp(*args)}, not {want}"
        for args, want in (
            ((5, 0, 10), 5),
            ((0, 0, 10), 0),
            ((10, 0, 10), 10),
            ((-3, 0, 10), 0),
            ((30, 0, 10), 10),
        )
        if clamp.clamp(*args) != want
    ]
    doc = re.sub(r"\s+", " ", clamp.clamp.__doc__ or "")
    if re.search(r"(?i)\bexclud", doc) and not re.search(
        r"(?i)\bnot excluded|\bnever excluded", doc
    ):
        lacking.append("the docstring still says the bounds are excluded")
    if not re.search(r"(?i)\binclu|\bbetween|\bclos", doc):
        lacking.append("the docstring does not say the bounds are included")
    return lacking


def disposition() -> list[str]:
    reviewed, current, kind = False, None, None
    for line in Path("reviews/clamp.md").read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading:
            current = heading.group(1).upper()
        elif current is None and re.match(r"^Reviewed: \S", line):
            reviewed = True
        elif current == "R1" and DISPOSITION.match(line):
            kind = "fixed"
    lacking = []
    if not reviewed:
        lacking.append("the file has no `Reviewed:` line above its finding")
    if kind != "fixed":
        lacking.append("R1 has no `Disposition: fixed — <where>` line")
    return lacking


def plain() -> list[str]:
    found = transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )
    if found is None:
        return [transcript_commands.UNKNOWN]
    return [
        f"a command installed something: {command[:80]}"
        for command in found
        if any(transcript_commands.executes(command, name) for name in INSTALLERS)
    ]


CHECKS = {"fixed": fixed, "disposition": disposition, "plain": plain}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_clamp.py {{{','.join(CHECKS)}}}")
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
