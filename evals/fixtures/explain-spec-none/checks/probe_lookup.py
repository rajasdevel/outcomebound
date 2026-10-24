#!/usr/bin/env python3
"""The explain-spec-none fixture's checks, read from the answer by a probe the model cannot edit.

    answered   the answer gives 30 as the delay between two attempts

It exits 0 where it holds and 1 naming what does not. Whether the answer quizzes the author is a
report item, read blind (`reading/no-quiz.md`). The answer is the file OUTCOMEBOUND_EVAL_ANSWER
names.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


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


CHECKS = {"answered": answered}


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
