#!/usr/bin/env python3
"""Read a decision brief's parts from a text: exit 0 where each is there, and 1 naming each
that is not. Lines starting `observed:` describe the rest and never change the exit status.

The text is the file named on the command line, or the one OUTCOMEBOUND_EVAL_ANSWER names.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Marks and dashes are written as escapes: \U0001F449 recommend, \U0001F53B downside, \u21a9 undo,
# \u26d4 cannot be undone; \u00b7 middle dot, \u2014 em dash, \u2013 en dash, \u2019 apostrophe.
_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s+|[-*+]\s+)?(?:\*\*)?(?:(?i:decision|question)\s+)?"
    r"[A-Za-z][A-Za-z0-9-]*(?:\*\*)?\s*[\u00b7:|.)\u2014\u2013-].*\?"
)
_OPTION = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|\s*)?(?:\*\*)?(?:(?i:option)\s+)?\(?(?P<letter>[A-J])\)?"
    r"(?:\*\*)?(?:[.:)]|\s*[|\u00b7\u2014\u2013-]|\s)\s*(?:\*\*)?\s*(?P<text>\S.*)$"
)
_RECOMMEND = re.compile(r"(?i)recommend|\U0001F449|\[>\]")
_BARE = re.compile(r"(?i)^[\W_]*recommend\w*[\W_]*$")
_LETTER = re.compile(r"(?<![\w'\u2019])([A-J])(?![\w'\u2019])")
_UNDO = re.compile(r"(?i)\bundo(?:ne|able)?\b|\b(?:ir)?reversib|\u21a9|\u26d4|\[undo\]|\[!!\]")
_DOWNSIDE = re.compile(r"(?i)\U0001F53B|\[-\]|\bdownsides?\b")


def _options(lines: list[str]) -> dict[str, str]:
    """The lettered options, A onwards without a gap, each with the start of its text."""

    found: dict[str, str] = {}
    for line in lines:
        match = _OPTION.match(line)
        if match:
            text = re.split(r"\s[-\u2014\u2013|:]\s|,", match["text"].replace("*", ""), maxsplit=1)
            found.setdefault(match["letter"], text[0].strip().lower()[:24])
    run: dict[str, str] = {}
    for letter in "ABCDEFGHIJ":
        if letter not in found:
            break
        run[letter] = found[letter]
    return run


def _names_option(text: str, options: dict[str, str]) -> bool:
    if set(_LETTER.findall(text)) & set(options):
        return True
    return any(start and start in text.lower() for start in options.values())


def _recommends(lines: list[str], options: dict[str, str]) -> bool:
    """Whether a recommendation names one of the options: on its own line, or on the line
    after a bare `Recommendation` heading."""

    for index, line in enumerate(lines):
        if not _RECOMMEND.search(line):
            continue
        if _names_option(line, options):
            return True
        following = next((text for text in lines[index + 1 :] if text.strip()), "")
        if _BARE.match(line) and _names_option(following, options):
            return True
    return False


def missing(text: str) -> list[str]:
    """Each part of the brief the text lacks, in the order a brief states them."""

    lines = text.splitlines()
    options = _options(lines)
    parts = [
        ("an id with its question on one line", any(_HEADING.match(line) for line in lines)),
        ("lettered options A and B", {"A", "B"} <= set(options)),
        ("a recommendation naming an option", _recommends(lines, options)),
        ("whether it can be undone", any(_UNDO.search(line) for line in lines)),
    ]
    return [part for part, present in parts if not present]


def observed(text: str) -> list[str]:
    """What the brief shows beyond those parts: downsides and a diagram."""

    lines = text.splitlines()
    downsides = sum(1 for line in lines if _DOWNSIDE.search(line))
    if re.search(r"(?m)^\s*```\s*mermaid", text):
        diagram = "a Mermaid diagram"
    elif any("-->" in line for line in lines):
        diagram = "an ASCII diagram"
    else:
        diagram = "no diagram"
    return [
        f"observed: {downsides} line(s) name a downside, for {len(_options(lines))} option(s)",
        f"observed: {diagram}",
    ]


def _main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    source = arguments[0] if arguments else os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")
    try:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    except OSError:
        print("no text was supplied to read a brief from")
        return 1
    lacking = missing(text)
    for part in lacking:
        print(f"missing: {part}")
    for line in observed(text):
        print(line)
    if not lacking:
        print("every part is there")
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main())
