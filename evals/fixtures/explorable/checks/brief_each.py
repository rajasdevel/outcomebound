#!/usr/bin/env python3
"""Read the answer for a decision brief on each of the two decisions: exit 0 where each has its
own brief with every part, and 1 naming each that has none. Lines starting `observed:` describe
the rest and never change the exit status.

The answer is split at each line that `brief.py` reads as an id with its question; a brief is
one such part that lacks no part `brief.py` requires. Each decision needs a different brief that
names it. The text is the file named on the command line, or the one OUTCOMEBOUND_EVAL_ANSWER
names.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from itertools import permutations
from pathlib import Path
from types import ModuleType


def _sibling(name: str) -> ModuleType:
    """The grader `name`.py beside this one."""

    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().with_name(f"{name}.py")
    )
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


brief = _sibling("brief")

DECISIONS = {
    "the uploads disk": re.compile(r"(?i)\bdisk|\buploads?\b|\barchiv"),
    "the old export endpoint": re.compile(r"(?i)export"),
}


def parts(text: str) -> list[str]:
    """The text from each line read as an id with its question to the next such line."""

    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if brief._HEADING.match(line)]
    ends = [*starts[1:], len(lines)]
    return ["\n".join(lines[start:end]) for start, end in zip(starts, ends, strict=True)]


def missing(text: str) -> list[str]:
    """Each decision the text gives no brief of its own."""

    complete = [part for part in parts(text) if not brief.missing(part)]
    names = list(DECISIONS)
    for chosen in permutations(complete, len(names)):
        if all(DECISIONS[name].search(part) for name, part in zip(names, chosen, strict=True)):
            return []
    lacking = [
        f"missing: a complete brief on {name}"
        for name in names
        if not [part for part in complete if DECISIONS[name].search(part)]
    ]
    return lacking or ["missing: one brief for each decision; a single brief covers both"]


def _main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    source = arguments[0] if arguments else os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")
    try:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    except OSError:
        print("no text was supplied to read a brief from")
        return 1
    print(f"observed: {len(parts(text))} line(s) read as an id with its question")
    for line in brief.observed(text):
        print(line)
    lacking = missing(text)
    for line in lacking:
        print(line)
    if not lacking:
        print("each decision has its brief")
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main())
