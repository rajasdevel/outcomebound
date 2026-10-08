#!/usr/bin/env python3
"""The requirements-replay fixture's checks, read from the workspace and the answer by a probe the
model cannot edit.

    behaviour   `to_csv` writes ISO dates, keeps the amounts in cents (the issue's correction),
                keeps the column order and leaves out a cancelled order, whatever the data
    kept        the answer, or a note the run wrote, names each of the four requirements the
                issue holds: the date format, the amounts, the cancelled orders and the order
                of the columns
    corrected   a line of the answer says that the later comment changed the amounts
    provenance  a line of the answer marks a requirement `stated`, and the report names the issue

The answer checks read lines for the words each must carry, not meaning. Each exits 0 where it
holds and 1 naming what does not. The answer is the file OUTCOMEBOUND_EVAL_ANSWER names.
"""

from __future__ import annotations

import os
import re
import runpy
import subprocess
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


def _text() -> str | None:
    """The answer, and the text of each new note the run left that git lists."""

    try:
        text = Path(os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None
    paths = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout.splitlines()
    for path in paths:
        if path.endswith((".md", ".txt")):
            try:
                text += "\n" + Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return text


NAMED = {
    "the ISO dates": r"(?i)\biso\b|yyyy-mm-dd|2026-03-04",
    "the amounts": r"(?i)amounts?|cents|euros?",
    "the cancelled orders": r"(?i)cancel",
    "the column order": r"(?i)column order|order of (the )?columns|by position|positional",
}


def kept() -> list[str]:
    text = _text()
    if text is None:
        return ["no answer was supplied"]
    return [
        f"the report does not name {what}"
        for what, rule in NAMED.items()
        if not re.search(rule, text)
    ]


CORRECTION = re.compile(
    r"(?i)correct|supersed|overrid|replac|instead|later comment|finance's comment"
)
AMOUNT = re.compile(r"(?i)cents|amounts?|\b2\b")


def corrected() -> list[str]:
    text = _text()
    if text is None:
        return ["no answer was supplied"]
    if any(CORRECTION.search(line) and AMOUNT.search(line) for line in text.splitlines()):
        return []
    return ["no line says that the later comment changed the amounts"]


SOURCE = re.compile(r"(?i)\bissue(?:[-_ ]+#?\s*|#)31\b")
STATED = re.compile(r"(?i)\bstated\b")
NEGATED_STATED = re.compile(
    r"(?i)\b(?:no|not|never)\s+(?:(?:explicitly|directly|clearly)\s+)?stated\b"
    r"|\b(?:isn't|wasn't|aren't|weren't)\s+stated\b"
)


_support = Path(__file__).resolve().parent / "report_records.py"
if not _support.is_file():
    _support = Path(__file__).resolve().parents[3] / "graders" / "report_records.py"
# run_path reads this protected source file without accepting candidate import caches.
_report_records = runpy.run_path(str(_support), run_name="report_records")
_records = _report_records["records"]


def provenance() -> list[str]:
    text = _text()
    if text is None:
        return ["no answer was supplied"]
    for record in _records(text):
        if (
            SOURCE.search(record)
            and STATED.search(record)
            and not NEGATED_STATED.search(record)
            and not re.search(r"(?i)\bnot\s+(?:from|in|by)\s+(?:source/)?issue", record)
            and any(re.search(rule, record) for rule in NAMED.values())
        ):
            return []
    return ["no positive stated requirement is bound to issue 31 in a report record"]


CHECKS = {
    "behaviour": behaviour,
    "kept": kept,
    "corrected": corrected,
    "provenance": provenance,
}


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
