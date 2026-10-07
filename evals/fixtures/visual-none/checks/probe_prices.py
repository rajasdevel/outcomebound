#!/usr/bin/env python3
"""The visual-none fixture's checks. The request holds no picture, so the skill's paragraph on
pictures adds nothing: the task is done and the answer and the commands carry no trace of it.

    behaviour  `format_range` returns the text the task describes
    quiet      the answer names no picture, screenshot or design export, and has no `reference`
               disposition row (`disposed`, `by: command|review|judgment`)
    plain      no command the run executed imported or checked a source ledger

Each exits 0 where it holds and 1 naming what does not. The answer is the file
OUTCOMEBOUND_EVAL_ANSWER names and the transcript the file OUTCOMEBOUND_EVAL_TRANSCRIPT names.
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

CASES = {
    (1000, 1200): "$10.00 to $12.00",
    (1200, 1200): "$12.00",
    (0, 5): "$0.00 to $0.05",
    (5, 5): "$0.05",
    (99, 100): "$0.99 to $1.00",
    (1999, 2500): "$19.99 to $25.00",
}
PICTURE = re.compile(r"(?i)\b(pictures?|screenshots?|mock-?ups?|pixels?|design exports?|images?)\b")
ROW = re.compile(
    r"(?i)\bby:\s*(command|review|judgment)\b|\bdisposed\b|\bdisposition\b.*\breference\b"
)
SOURCES = re.compile(r"\bsources\s+(import|check)\b")


def behaviour() -> list[str]:
    spec = importlib.util.spec_from_file_location("prices", Path.cwd() / "prices.py")
    if spec is None or spec.loader is None:
        return ["no prices.py in the working directory"]
    prices = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prices)
    if not hasattr(prices, "format_range"):
        return ["prices.py has no format_range"]
    lacking = [
        f"format_range{pair} is {prices.format_range(*pair)!r}, not {want!r}"
        for pair, want in CASES.items()
        if prices.format_range(*pair) != want
    ]
    if prices.format_price(1200) != "$12.00":
        lacking.append("format_price changed")
    return lacking


def quiet() -> list[str]:
    try:
        text = Path(os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return ["no answer was supplied"]
    lacking = []
    found = PICTURE.search(text)
    if found:
        lacking.append(f"the answer speaks of a picture: {found.group(0)!r}")
    if ROW.search(text):
        lacking.append("the answer has a reference or disposition row")
    return lacking


def plain() -> list[str]:
    found = transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )
    if found is None:
        return [transcript_commands.UNKNOWN]
    return [
        f"a command imported or checked a source: {command[:80]}"
        for command in found
        if SOURCES.search(command)
    ]


CHECKS = {"behaviour": behaviour, "quiet": quiet, "plain": plain}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_prices.py {{{','.join(CHECKS)}}}")
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
