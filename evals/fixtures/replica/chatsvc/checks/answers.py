#!/usr/bin/env python3
"""Reading an answer or a note for facts: clauses, negation, counts, digests and ledger lines.

The graders of the chatsvc fixtures grade what a text asserts, not which words it uses: a fact
counts where a clause asserts it and does not negate it, and a clause that asserts the opposite
fails the fact. These helpers are deliberately small and literal; their tests, in
tests/test_replica_graders.py, hold paraphrased, negated and contradictory answers.

Standard library only.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ANSWER_ENV = "OUTCOMEBOUND_EVAL_ANSWER"

NEGATION = re.compile(
    r"\b(not|never|no longer|cannot|can't|isn't|aren't|wasn't|weren't|didn't|doesn't|don't|"
    r"won't|hasn't|haven't|failed to|unable to|no)\b",
    re.IGNORECASE,
)
# A clause ends at a sentence end, a semicolon, a dash between words, or a line end.
_DASHES = "\u2014\u2013"
_CLAUSE = re.compile(rf"(?<=[.!?])\s+(?=[A-Z`(\"'*])|;\s*|\s+[{_DASHES}]\s+|\s+-\s+|\n")
_MARKUP = re.compile(r"^\s*(?:[-*+>]|\d+[.)])\s+|[*_`]+")
VERDICT = r"(?:PASS(?:ED)?|FAIL(?:ED)?|UNVERIFIED)"
_LEDGER = (
    re.compile(rf"^{VERDICT}\b"),
    re.compile(rf"(?:^|[:={_DASHES}-]\s*|\(){VERDICT}\)?\.?$"),
)
DIGEST = re.compile(
    r"(?<![0-9A-Za-z_])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,64}(?![0-9A-Za-z_])"
)
INTERNAL_ID = re.compile(r"\b(?:fb|c)_[0-9a-f]{6,}\b")
_NUMBER = re.compile(r"(?<![\w.,/#:$-])(\d{1,5})(?![\w%]|[.,:/-]\d)")
_NOT_A_COUNT = re.compile(
    r"^\s*(?:s|sec|secs|second|seconds|ms|min|mins|minute|minutes|h|hours?|days?|tokens?|"
    r"words?|inputs?|kb?|mb?|%)\b",
    re.IGNORECASE,
)


WORD_NUMBERS = {
    word: n
    for n, word in enumerate(
        [
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
        ],
        start=1,
    )
}
# A number in words counts only where a counted noun follows it ("Five people", "two reports"),
# so "the main one" is not a count.
_WORD_COUNT = re.compile(
    rf"\b({'|'.join(WORD_NUMBERS)})\s+(?:\w+\s+)?(conversations?|people|persons?|users?|"
    r"reports?|complaints?|cases?|chats?|ratings?|submissions?|customers?|times)\b",
    re.I,
)


def read_answer(path: str | None = None) -> str | None:
    """The final answer the runner saved, or None where none was supplied."""

    name = path or os.environ.get(ANSWER_ENV, "")
    if not name or not Path(name).is_file():
        return None
    return Path(name).read_text(encoding="utf-8", errors="replace")


def plain(line: str) -> str:
    """A line without list markers, emphasis or code ticks."""

    return _MARKUP.sub("", line).strip()


def clauses(text: str) -> list[str]:
    """The clauses of a text, each without markup."""

    found = []
    for part in _CLAUSE.split(text):
        cleaned = plain(part)
        if cleaned and not set(cleaned) <= set("|-: "):
            found.append(cleaned)
    return found


def negated(clause: str, before: str) -> bool:
    """Whether a negation stands in `clause` before the first match of `before`."""

    match = re.search(before, clause, re.IGNORECASE)
    head = clause[: match.start()] if match else clause
    return bool(NEGATION.search(head))


def ledger_lines(text: str) -> list[str]:
    """The lines that are a bare verdict about a check: a verdict word that opens or closes the
    line, or a table cell that holds nothing else. A verdict word inside a sentence is not one."""

    found = []
    for raw in text.splitlines():
        line = plain(raw)
        if not line:
            continue
        cells = [plain(cell) for cell in line.strip("|").split("|")] if "|" in line else []
        bare_cell = any(re.fullmatch(VERDICT, cell) for cell in cells)
        if bare_cell or any(pattern.search(line) for pattern in _LEDGER):
            found.append(raw)
    return found


def digests(text: str) -> list[str]:
    """Hex digests (seven or more hex characters, with a letter and a digit) and the store's
    internal ids (`fb_...`, `c_...`)."""

    return sorted(set(DIGEST.findall(text)) | set(INTERNAL_ID.findall(text)))


def counts(line: str) -> list[int]:
    """The numbers in a line that can be counts: not a version, a date, a time, a decimal, a
    percentage, a reference such as #12, a list marker, or a number of seconds or tokens; and
    one to twelve in words before a counted noun."""

    line = re.sub(r"^\s*(?:[-*+>]\s+)?\d+[.)]\s+", "", line)
    found = []
    for match in _NUMBER.finditer(line):
        if _NOT_A_COUNT.match(line[match.end() :]):
            continue
        found.append(int(match.group(1)))
    found.extend(WORD_NUMBERS[match.group(1).lower()] for match in _WORD_COUNT.finditer(line))
    return found
