#!/usr/bin/env python3
"""Read a decision brief's parts from a text: exit 0 where each is there, and 1 naming each
that is not. Lines starting `observed:` describe the rest and never change the exit status.

The recommendation and the undo are read as drawn fields, never as words in a sentence: a line
whose label (after any list marker, bold or other mark) is a recommend mark (`Recommend...`, the
star, the pointing hand, `[>]`) and that names an option, or that stands under an option or over
a line that names one; and a line whose label is an undo mark (`Undo`, the return arrow, the no
entry mark, `[undo]`, `[!!]`, `Can be undone`, `Reversible`). "I have no recommendation between A
and B" and "I have not checked whether either option is reversible" are no fields.

The text is the file named on the command line, or the one OUTCOMEBOUND_EVAL_ANSWER names.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Marks and dashes are written as escapes: \U0001F449 the recommend mark of the earlier shape,
# \u2b50 recommended, \U0001F53B downside, \u21a9 undo, \u26d4 cannot be undone; \u00b7 middle dot,
# \u2014 em dash, \u2013 en dash, \u2019 apostrophe.
_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s+|[-*+]\s+)?(?:\*\*)?(?:(?i:decision|question)\s+)?"
    r"[A-Za-z][A-Za-z0-9-]*(?:\*\*)?\s*[\u00b7:|.)\u2014\u2013-].*\?"
)
_OPTION = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|\s*)?(?:\*\*)?(?:(?i:option)\s+)?\(?(?P<letter>[A-J])\)?"
    r"(?:\*\*)?(?:[.:)]|\s*[|\u00b7\u2014\u2013-]|\s)\s*(?:\*\*)?\s*(?P<text>\S.*)$"
)
# The start of a field line: indentation, a list marker, bold, and any marks before its label (a
# bracketed ASCII mark such as `[rec]`, or a run of symbols such as an emoji).
_FIELD = (
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:\*\*|__)?\s*(?:(?:\[[^\]\s]{1,8}\]|[^\x00-\x7f\w\s]+)\s*)*?"
)
# A word label counts only as a field: the label, then a separator (`Recommended: A`) or the end of
# its line (a bare label over the line that names the option), so a sentence that starts with the
# word ("Recommending A now would be premature") is no field.
_SEPARATOR = r"(?:\*\*|__)?\s*[:\u2014\u2013-]"
_RECOMMEND = re.compile(
    _FIELD
    + r"(?:(?i:recommend(?:ed|ation)?)(?:"
    + _SEPARATOR
    + r"|(?:\*\*|__)?\s*$)|\u2b50|\U0001F449|\[>\])"
)
# The lead-in of the options: `**Options**` of the current shape, `- Options:` of the earlier one.
_OPTIONS_LEAD = re.compile(r"(?i)^\s*(?:[-*+]\s+)?(?:\*\*)?options(?:\*\*)?:?\s*$")
_BARE = re.compile(r"(?i)^[\W_]*recommend(?:ed|ation)?[\W_]*$")
_LETTER = re.compile(r"(?<![\w'\u2019])([A-J])(?![\w'\u2019])")
_UNDO = re.compile(
    _FIELD
    + r"(?:(?i:undo|can(?:not|'t|\u2019t| not)? be undone|(?:ir)?reversible)"
    + _SEPARATOR
    + r"|\u21a9|\u26d4|\[undo\]|\[!!\])"
)
_DOWNSIDE = re.compile(r"(?i)\U0001F53B|\[-\]|\bdownsides?\b")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _option_lines(lines: list[str]) -> list[int]:
    """The indexes of the lines that may be options: where the text has an options lead-in, the
    list under it, which a blank line ends unless an option or a deeper line follows it; else
    every line."""

    leads = [at for at, line in enumerate(lines) if _OPTIONS_LEAD.match(line)]
    if not leads:
        return list(range(len(lines)))
    found: list[int] = []
    for lead in leads:
        at = lead + 1
        while at < len(lines) and not lines[at].strip():
            at += 1
        start = _indent(lines[at]) if at < len(lines) else 0
        while at < len(lines):
            if lines[at].strip():
                found.append(at)
                at += 1
                continue
            following = next((n for n in range(at, len(lines)) if lines[n].strip()), None)
            if following is None or not (
                _OPTION.match(lines[following]) or _indent(lines[following]) > start
            ):
                break
            at = following
    return found


def _options(lines: list[str]) -> dict[str, str]:
    """The lettered options, A onwards without a gap, each with the start of its text. Where the
    text has an options lead-in, only the list under it is read, so a context list that starts
    with a capital letter is not an option."""

    found: dict[str, str] = {}
    for at in _option_lines(lines):
        match = _OPTION.match(lines[at])
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


def _nested_under_option(lines: list[str], index: int, options: dict[str, str]) -> bool:
    """Whether the line at `index` is indented under an option of the list: the nearest
    shallower line above it is one of the options."""

    own = _indent(lines[index])
    candidates = set(_option_lines(lines))
    for above in range(index - 1, -1, -1):
        line = lines[above]
        if not line.strip():
            return False
        if _indent(line) < own:
            match = _OPTION.match(line) if above in candidates else None
            return match is not None and match["letter"] in options
    return False


def _recommends(lines: list[str], options: dict[str, str]) -> bool:
    """Whether a recommendation field names one of the options: on its own line, under the
    option it stands under, or on the line after a bare `Recommendation` label."""

    for index, line in enumerate(lines):
        if not _RECOMMEND.match(line):
            continue
        if _names_option(line, options) or _nested_under_option(lines, index, options):
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
        ("whether it can be undone", any(_UNDO.match(line) for line in lines)),
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
