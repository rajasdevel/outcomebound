#!/usr/bin/env python3
"""The explain-spec-none fixture's checks, read from the answer by a probe the model cannot edit.

    answered   the answer gives 30 as the delay between two attempts
    quiet      the answer holds no quiz of the person (a `why not` question, a request to predict,
               a check of understanding) and no `UNVERIFIED` report of their understanding

Each exits 0 where it holds and 1 naming what does not. The answer checks read the words each
must or must not carry, not meaning. The answer is the file OUTCOMEBOUND_EVAL_ANSWER names.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

QUIZ = re.compile(
    r"(?i)why not|why does it not|what (would|do you think|happens)|predict|quiz"
    r"|check (your|that you)|test your|did you (follow|understand)|understand(ing)? (it|the design)"
)


def _answer() -> str | None:
    try:
        return Path(os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None


def answered() -> list[str]:
    text = _answer()
    if text is None:
        return ["no answer was supplied"]
    if re.search(r"\b30\b", text):
        return []
    return ["the answer does not give the delay, 30 seconds"]


def quiet() -> list[str]:
    text = _answer()
    if text is None:
        return ["no answer was supplied"]
    lacking = [
        f"the answer quizzes the person: {line.strip()[:80]!r}"
        for line in text.splitlines()
        if QUIZ.search(line)
    ]
    if re.search(
        r"UNVERIFIED[^\n]*(understand|understood|follow|grasp)|(understand|understood|follow|grasp)[^\n]*UNVERIFIED",
        text,
    ):
        lacking.append("the answer reports the person's understanding as UNVERIFIED")
    return lacking


CHECKS = {"answered": answered, "quiet": quiet}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_lookup.py {{{','.join(CHECKS)}}}")
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
